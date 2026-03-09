import { createContext, useContext, useEffect, useState, type ReactNode } from "react";

import {
  PRINCIPAL_SESSION_CHANGE_EVENT,
  clearStoredPrincipalName,
  getStoredPrincipalName,
  setStoredPrincipalName
} from "./principalStorage";

interface PrincipalSessionContextValue {
  principalName: string | null;
  setPrincipalName: (value: string) => void;
  clearPrincipalName: () => void;
}

const PrincipalSessionContext = createContext<PrincipalSessionContextValue | null>(null);

export function PrincipalSessionProvider({ children }: { children: ReactNode }) {
  const [principalName, setPrincipalNameState] = useState<string | null>(() => getStoredPrincipalName());

  useEffect(() => {
    if (typeof window === "undefined") {
      return undefined;
    }

    function syncPrincipalName() {
      setPrincipalNameState(getStoredPrincipalName());
    }

    window.addEventListener(PRINCIPAL_SESSION_CHANGE_EVENT, syncPrincipalName);
    return () => {
      window.removeEventListener(PRINCIPAL_SESSION_CHANGE_EVENT, syncPrincipalName);
    };
  }, []);

  return (
    <PrincipalSessionContext.Provider
      value={{
        principalName,
        setPrincipalName(value: string) {
          setPrincipalNameState(setStoredPrincipalName(value));
        },
        clearPrincipalName() {
          clearStoredPrincipalName();
          setPrincipalNameState(getStoredPrincipalName());
        }
      }}
    >
      {children}
    </PrincipalSessionContext.Provider>
  );
}

export function usePrincipalSession(): PrincipalSessionContextValue {
  const context = useContext(PrincipalSessionContext);
  if (context === null) {
    throw new Error("usePrincipalSession must be used within a PrincipalSessionProvider.");
  }
  return context;
}
