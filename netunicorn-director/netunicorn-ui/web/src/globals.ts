// netUnicorn api url, uses nginx and envsubst for inserting the correct value from the environment
// change manually if needed
// e.g., for local development: http://localhost:26611

export const NETUNICORN_MEDIATOR_URL: string = (window as any).NETUNICORN_MEDIATOR_URL;
