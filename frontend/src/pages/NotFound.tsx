import { PageHeading } from '../components/ui';
export function NotFound() {
  return <><PageHeading eyebrow="PAGE NOT FOUND" title="This route isn’t in the workspace.">Use the navigation to return to a supported page.</PageHeading><a className="button" href="#/">Back to overview</a></>;
}
