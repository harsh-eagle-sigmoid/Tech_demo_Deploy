/**
 * Azure AD MSAL Configuration
 *
 * This file configures MSAL (Microsoft Authentication Library) for Azure AD
 * authentication in the React dashboard.
 *
 * To enable authentication:
 * 1. Create an App Registration in Azure Portal
 * 2. Set the values below from your App Registration
 * 3. Set AUTH_ENABLED=true in the backend .env
 */

// Configuration will be loaded from backend API
export const msalConfig = {
  auth: {
    clientId: "", // Will be set dynamically from API
    authority: "", // Will be set dynamically from API
    redirectUri: window.location.origin,
    postLogoutRedirectUri: window.location.origin,
    navigateToLoginRequestUrl: true,
  },
  cache: {
    cacheLocation: "localStorage",
    storeAuthStateInCookie: false, // Set to true for IE11 support
  },
  system: {
    loggerOptions: {
      loggerCallback: (level, message, containsPii) => {
        if (containsPii) return;
        switch (level) {
          case 0: console.error(message); break;
          case 1: console.warn(message); break;
          case 2: console.info(message); break;
          case 3: console.debug(message); break;
          default: break;
        }
      },
      logLevel: 3, // Info
    },
  },
};

// Scopes for access token
export const loginRequest = {
  scopes: [], // Will be set dynamically from API
};

// API endpoint scopes
export const apiRequest = {
  scopes: [], // Will be set dynamically from API
};

/**
 * Initialize MSAL config from backend API
 */
export async function loadAuthConfig() {
  try {
    const response = await fetch("/api/v1/auth/config");
    const config = await response.json();

    if (!config.auth_enabled) {
      return { authEnabled: false };
    }

    msalConfig.auth.clientId = config.client_id;
    msalConfig.auth.authority = config.authority;

    loginRequest.scopes = config.scopes || [];
    apiRequest.scopes = config.scopes || [];

    return {
      authEnabled: true,
      config: msalConfig,
      loginRequest,
      apiRequest
    };
  } catch (error) {
    console.warn("Failed to load auth config:", error);
    return { authEnabled: false };
  }
}
