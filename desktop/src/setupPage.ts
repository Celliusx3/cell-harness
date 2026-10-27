interface Window {
  readonly cellSetup: import("./setupPreload").CellSetup;
}

function elementById<T extends HTMLElement>(id: string, kind: new () => T): T {
  const element = document.getElementById(id);
  if (!(element instanceof kind)) throw new Error(`setup.html has no ${kind.name} #${id}`);
  return element;
}

function errorText(error: unknown): string {
  return error instanceof Error ? error.message : String(error);
}

const setupForm = elementById("setup", HTMLFormElement);
const apiKeyInput = elementById("api-key", HTMLInputElement);
const baseUrlInput = elementById("base-url", HTMLInputElement);
const modelInput = elementById("model", HTMLInputElement);
const startButton = elementById("start", HTMLButtonElement);
const errorLine = elementById("error", HTMLElement);

function showError(message: string): void {
  errorLine.textContent = message;
  startButton.disabled = false;
}

async function fillDefaults(): Promise<void> {
  const endpoint = await window.cellSetup.defaults();
  baseUrlInput.value = endpoint.baseUrl;
  modelInput.value = endpoint.model;
}

async function saveAnswers(): Promise<void> {
  startButton.disabled = true;
  errorLine.textContent = "";
  const result = await window.cellSetup.save({
    apiKey: apiKeyInput.value,
    baseUrl: baseUrlInput.value,
    model: modelInput.value,
  });
  if (!result.ok) showError(result.error);
}

setupForm.addEventListener("submit", (event) => {
  event.preventDefault();
  saveAnswers().catch((error: unknown) => showError(errorText(error)));
});
fillDefaults().catch((error: unknown) => showError(errorText(error)));
