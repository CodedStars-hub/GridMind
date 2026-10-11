"""Local structural/security checks; these do not replace SAM/CloudFormation validation."""

import json
from pathlib import Path
import re
import subprocess
import sys
import zipfile

import pytest

ROOT = Path(__file__).resolve().parents[2]
TEMPLATE = ROOT / 'infra/template.json'


@pytest.fixture
def template():
    return json.loads(TEMPLATE.read_text(encoding='utf-8'))


def test_template_is_small_sam_with_only_api_resources(template):
    assert template['AWSTemplateFormatVersion'] == '2010-09-09'
    assert template['Transform'] == 'AWS::Serverless-2016-10-31'
    assert len(template['Description'].encode()) < 1024
    assert TEMPLATE.stat().st_size < 51200
    assert sorted(r['Type'] for r in template['Resources'].values()) == sorted([
        'AWS::Logs::LogGroup', 'AWS::IAM::Role', 'AWS::Serverless::Function',
        'AWS::Serverless::HttpApi', 'AWS::Lambda::Permission'])
    assert set(template['Parameters']) == {'AllowedOriginsJson'}
    assert json.loads(template['Parameters']['AllowedOriginsJson']['Default']) == []


def test_runtime_package_and_budget(template):
    function = template['Resources']['GridMindFunction']['Properties']
    assert function['Handler'] == 'handler.lambda_handler'
    assert function['Runtime'] == 'python3.12'
    assert function['Architectures'] == ['x86_64']
    assert function['Role'] == {'Fn::GetAtt': ['GridMindRole', 'Arn']}
    assert 'Policies' not in function and 'Events' not in function
    assert function['MemorySize'] == 2048
    assert function['Timeout'] == 25
    assert (TEMPLATE.parent / function['CodeUri']).resolve() == ROOT / 'out/gridmind-api.zip'
    assert function['Environment']['Variables'] == {'GRIDMIND_ALLOWED_ORIGINS': {'Ref': 'AllowedOriginsJson'}}
    assert not any(k in function for k in ('VpcConfig', 'Layers', 'FunctionUrlConfig', 'DeadLetterQueue'))


def test_single_default_proxy_preserves_all_methods_and_paths(template):
    api = template['Resources']['GridMindHttpApi']['Properties']
    assert api['StageName'] == '$default'
    assert api['DefaultRouteSettings'] == {'ThrottlingRateLimit': 1, 'ThrottlingBurstLimit': 2}
    # Lambda already owns approved-origin CORS; no conflicting gateway policy.
    assert 'CorsConfiguration' not in api
    paths = api['DefinitionBody']['paths']
    assert set(paths) == {'/$default'}
    route = paths['/$default']['x-amazon-apigateway-any-method']
    assert route['isDefaultRoute'] is True
    integration = route['x-amazon-apigateway-integration']
    assert integration['type'] == 'aws_proxy' and integration['httpMethod'] == 'POST'
    assert integration['payloadFormatVersion'] == '2.0'
    assert integration['uri'] == {'Fn::GetAtt': ['GridMindFunction', 'Arn']}
    assert integration['timeoutInMillis'] == 29000
    assert integration['timeoutInMillis'] > template['Resources']['GridMindFunction']['Properties']['Timeout'] * 1000


def test_runtime_iam_is_own_log_streams_only(template):
    role = template['Resources']['GridMindRole']['Properties']
    assert 'ManagedPolicyArns' not in role
    trust = role['AssumeRolePolicyDocument']['Statement']
    assert trust == [{'Effect': 'Allow', 'Principal': {'Service': 'lambda.amazonaws.com'}, 'Action': 'sts:AssumeRole'}]
    assert len(role['Policies']) == 1
    statements = role['Policies'][0]['PolicyDocument']['Statement']
    assert statements == [{'Effect': 'Allow', 'Action': ['logs:CreateLogStream', 'logs:PutLogEvents'],
                           'Resource': {'Fn::GetAtt': ['GridMindLogs', 'Arn']}}]
    logs = template['Resources']['GridMindLogs']
    assert logs['Properties']['RetentionInDays'] == 14
    assert logs['DeletionPolicy'] == logs['UpdateReplacePolicy'] == 'Retain'
    assert logs['Properties']['LogGroupName'] == {'Fn::Sub': '/aws/lambda/${AWS::StackName}-api'}
    assert template['Resources']['GridMindFunction']['Properties']['FunctionName'] == {'Fn::Sub': '${AWS::StackName}-api'}


def test_invocation_permission_scoped_to_account_api_and_stage(template):
    permission = template['Resources']['GridMindInvokePermission']['Properties']
    assert permission['Principal'] == 'apigateway.amazonaws.com'
    assert permission['Action'] == 'lambda:InvokeFunction'
    assert permission['FunctionName'] == {'Ref': 'GridMindFunction'}
    assert permission['SourceAccount'] == {'Ref': 'AWS::AccountId'}
    assert permission['SourceArn']['Fn::Sub'] == 'arn:${AWS::Partition}:execute-api:${AWS::Region}:${AWS::AccountId}:${GridMindHttpApi}/$default/*'


def dependencies(node):
    """Walk actual intrinsics rather than assume the expected dependency order."""
    if isinstance(node, list):
        return set().union(*(dependencies(v) for v in node)) if node else set()
    if not isinstance(node, dict):
        return set()
    refs = set()
    for key, value in node.items():
        if key == 'Ref':
            refs.add(value)
        elif key == 'Fn::GetAtt':
            refs.add(value[0] if isinstance(value, list) else value.split('.')[0])
        elif key == 'Fn::Sub':
            refs.update(v.split('.')[0] for v in re.findall(r'\$\{([^}]+)\}', value))
        else:
            refs.update(dependencies(value))
    return refs


def test_no_missing_references_or_circular_resource_dependencies(template):
    resources = template['Resources']
    pseudo = {'AWS::StackName', 'AWS::Region', 'AWS::Partition', 'AWS::AccountId', 'AWS::URLSuffix'}
    known = set(resources) | set(template['Parameters']) | pseudo
    assert dependencies(template) <= known
    graph = {}
    for name, resource in resources.items():
        explicit = resource.get('DependsOn', [])
        if isinstance(explicit, str):
            explicit = [explicit]
        graph[name] = (dependencies(resource) | set(explicit)) & set(resources)
    visiting, finished = set(), set()
    def visit(name):
        assert name not in visiting, f'Circular dependency at {name}'
        if name in finished:
            return
        visiting.add(name)
        for reference in graph[name]:
            visit(reference)
        visiting.remove(name)
        finished.add(name)
    for name in graph:
        visit(name)


def test_outputs_do_not_invent_account_or_endpoint(template):
    url = template['Outputs']['ApiBaseUrl']['Value']['Fn::Sub']
    assert url == 'https://${GridMindHttpApi}.execute-api.${AWS::Region}.${AWS::URLSuffix}'
    assert all('Description' in output for output in template['Outputs'].values())
    assert not any('Export' in output for output in template['Outputs'].values())
    assert not re.search(r'\b\d{12}\b', TEMPLATE.read_text())


def test_template_package_runs_health_and_cors_without_repo_paths(template, tmp_path):
    package_path = tmp_path / 'api.zip'
    subprocess.run([sys.executable, str(ROOT / 'scripts/package_api.py'), '--out', str(package_path)], check=True, capture_output=True)
    folder = tmp_path / 'deployment'
    with zipfile.ZipFile(package_path) as archive:
        names = archive.namelist()
        assert len([n for n in names if n.startswith('config/')]) == 14
        assert len([n for n in names if n.startswith('config/profiles/')]) == 7
        for path in (ROOT / 'engine/gridmind_engine').glob('*.py'):
            assert archive.read('gridmind_engine/' + path.name) == path.read_bytes()
        for path in (ROOT / 'config').rglob('*.json'):
            assert archive.read(path.relative_to(ROOT).as_posix()) == path.read_bytes()
        archive.extractall(folder)
    code = '''
import json, os, handler
os.environ['GRIDMIND_ALLOWED_ORIGINS'] = '["https://approved.example"]'
event = dict(version='2.0', rawPath='/api/v2/health', requestContext={'http': {'method': 'GET'}}, headers={}, body=None, isBase64Encoded=False)
health = handler.lambda_handler(event, None)
event['rawPath'] = '/api/v2/plan'
event['requestContext']['http']['method'] = 'OPTIONS'
event['headers'] = {'origin': 'https://approved.example', 'access-control-request-method': 'POST'}
preflight = handler.lambda_handler(event, None)
print(json.dumps([health, preflight]))
'''
    result = subprocess.run([sys.executable, '-I', '-c', 'import sys; sys.path.insert(0,' + repr(str(folder)) + ');' + code],
                            cwd=folder, capture_output=True, text=True, check=True)
    health, preflight = json.loads(result.stdout)
    assert health['statusCode'] == 200 and json.loads(health['body'])['api_version'] == 'v2'
    assert preflight['statusCode'] == 204 and preflight['body'] == ''
    assert preflight['headers']['Access-Control-Allow-Origin'] == 'https://approved.example'
    assert 'Access-Control-Allow-Credentials' not in preflight['headers']
