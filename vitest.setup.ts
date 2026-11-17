// React only enables act() support when this global is set. Without it every
// act() call logs "The current testing environment is not configured to
// support act(...)".
declare global {
  // eslint-disable-next-line no-var
  var IS_REACT_ACT_ENVIRONMENT: boolean;
}

globalThis.IS_REACT_ACT_ENVIRONMENT = true;

export {};
