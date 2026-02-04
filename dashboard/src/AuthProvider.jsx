/**
 * Azure AD Authentication Provider
 *
 * Wraps the application with MSAL authentication context.
 * When AUTH_ENABLED=false in backend, auth is bypassed.
 */
import { useState, useEffect, createContext, useContext } from "react";
import { PublicClientApplication, InteractionStatus } from "@azure/msal-browser";
import { MsalProvider, useMsal, useIsAuthenticated } from "@azure/msal-react";
import { loadAuthConfig, loginRequest } from "./authConfig";
import { setAccessToken as setApiAccessToken } from "./api";

// Context for auth state
const AuthContext = createContext({
  isLoading: true,
  authEnabled: false,
  user: null,
  accessToken: null,
  login: () => {},
  logout: () => {},
});

export const useAuth = () => useContext(AuthContext);

// Inner component that uses MSAL hooks
function AuthConsumer({ children, authEnabled }) {
  const { instance, accounts, inProgress } = useMsal();
  const isAuthenticated = useIsAuthenticated();
  const [accessToken, setAccessToken] = useState(null);

  // Get access token when authenticated
  useEffect(() => {
    if (isAuthenticated && accounts.length > 0) {
      instance
        .acquireTokenSilent({
          ...loginRequest,
          account: accounts[0],
        })
        .then((response) => {
          setAccessToken(response.accessToken);
          // Set token in API client for authenticated requests
          setApiAccessToken(response.accessToken);
        })
        .catch((error) => {
          console.error("Token acquisition failed:", error);
        });
    } else {
      // Clear token when not authenticated
      setApiAccessToken(null);
    }
  }, [isAuthenticated, accounts, instance]);

  const login = () => {
    instance.loginRedirect(loginRequest).catch((error) => {
      console.error("Login failed:", error);
    });
  };

  const logout = () => {
    instance.logoutRedirect().catch((error) => {
      console.error("Logout failed:", error);
    });
  };

  const user = accounts.length > 0 ? {
    name: accounts[0].name || accounts[0].username,
    email: accounts[0].username,
    id: accounts[0].localAccountId,
  } : null;

  const isLoading = inProgress !== InteractionStatus.None;

  return (
    <AuthContext.Provider
      value={{
        isLoading,
        authEnabled,
        user,
        accessToken,
        login,
        logout,
        isAuthenticated,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

// Component for when auth is disabled
function NoAuthProvider({ children }) {
  return (
    <AuthContext.Provider
      value={{
        isLoading: false,
        authEnabled: false,
        user: { name: "Anonymous", email: null },
        accessToken: null,
        login: () => {},
        logout: () => {},
        isAuthenticated: false,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

// Main Auth Provider
export default function AuthProvider({ children }) {
  const [isInitializing, setIsInitializing] = useState(true);
  const [authEnabled, setAuthEnabled] = useState(false);
  const [msalInstance, setMsalInstance] = useState(null);
  const [initError, setInitError] = useState(null);

  useEffect(() => {
    loadAuthConfig()
      .then((result) => {
        setAuthEnabled(result.authEnabled);
        if (result.authEnabled && result.config) {
          const instance = new PublicClientApplication(result.config);
          instance.initialize().then(() => {
            setMsalInstance(instance);
            setIsInitializing(false);
          });
        } else {
          setIsInitializing(false);
        }
      })
      .catch((error) => {
        console.error("Auth init failed:", error);
        setInitError(error);
        setIsInitializing(false);
      });
  }, []);

  if (isInitializing) {
    return (
      <div className="auth-loading">
        <p className="loading">Initializing authentication...</p>
      </div>
    );
  }

  if (initError) {
    console.warn("Auth initialization error, running without auth:", initError);
    return <NoAuthProvider>{children}</NoAuthProvider>;
  }

  if (!authEnabled) {
    return <NoAuthProvider>{children}</NoAuthProvider>;
  }

  return (
    <MsalProvider instance={msalInstance}>
      <AuthConsumer authEnabled={authEnabled}>
        {children}
      </AuthConsumer>
    </MsalProvider>
  );
}

// Login button component
export function LoginButton() {
  const { authEnabled, isAuthenticated, user, login, logout, isLoading } = useAuth();

  if (!authEnabled) {
    return null;
  }

  if (isLoading) {
    return <span className="auth-status">Loading...</span>;
  }

  if (isAuthenticated) {
    return (
      <div className="auth-user">
        <span className="user-name">{user?.name}</span>
        <button onClick={logout} className="btn-logout">
          Sign Out
        </button>
      </div>
    );
  }

  return (
    <button onClick={login} className="btn-login">
      Sign In with Azure AD
    </button>
  );
}

// Protected route wrapper
export function RequireAuth({ children }) {
  const { authEnabled, isAuthenticated, isLoading, login } = useAuth();

  if (!authEnabled) {
    return children;
  }

  if (isLoading) {
    return <p className="loading">Authenticating...</p>;
  }

  if (!isAuthenticated) {
    return (
      <div className="auth-required">
        <h2>Authentication Required</h2>
        <p>Please sign in with your Azure AD account to access this application.</p>
        <button onClick={login} className="btn-login">
          Sign In with Azure AD
        </button>
      </div>
    );
  }

  return children;
}
