/**
 * Typed access to build-time configuration.
 *
 * Environment variables are read here and nowhere else, so there is one place to
 * look when a value is wrong, and no component depends on `import.meta.env`
 * directly.
 */

/** Where the API lives. Relative by default so the dev proxy and the production
 *  nginx reverse proxy both work without a rebuild. */
export const API_BASE_URL: string = import.meta.env.VITE_API_BASE_URL ?? '/api/v1';

export const IS_DEVELOPMENT: boolean = import.meta.env.DEV;
