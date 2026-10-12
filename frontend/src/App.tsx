import { Library } from "./Library";
import { SystemProblem, useHealth } from "./SystemProblem";

export function App() {
  const health = useHealth();
  if (health?.ok === false) {
    return <SystemProblem health={health} />;
  }
  return <Library />;
}
