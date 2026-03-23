"use client";

import React, {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useState,
} from "react";

import { apiFetch, clearToken, getToken, setToken } from "@/lib/api";

export interface User {
  id: string;
  email: string;
  full_name: string | null;
  account_id: string;
}

export interface Account {
  id: string;
  company_name: string | null;
  currency: string;
  timezone: string;
  language: string;
  resend_inbound_address: string | null;
  first_import_at: string | null;
  last_import_at: string | null;
}

interface AuthContextType {
  user: User | null;
  account: Account | null;
  isLoading: boolean;
  login: (email: string, password: string) => Promise<void>;
  register: (email: string, password: string) => Promise<void>;
  logout: () => void;
  refreshAccount: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [account, setAccount] = useState<Account | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  const fetchMe = useCallback(async () => {
    try {
      const data = await apiFetch<{ user: User; account: Account }>("/auth/me");
      setUser(data.user);
      setAccount(data.account);
    } catch (error) {
      if (error instanceof Error && error.message === "Session expired") {
        setUser(null);
        setAccount(null);
      }
    }
  }, []);

  useEffect(() => {
    const token = getToken();

    if (token) {
      fetchMe().finally(() => setIsLoading(false));
      return;
    }

    setIsLoading(false);
  }, [fetchMe]);

  const login = async (email: string, password: string) => {
    const data = await apiFetch<{ access_token: string; user: User }>(
      "/auth/login",
      {
        method: "POST",
        body: JSON.stringify({ email, password }),
      },
      "none",
    );

    setToken(data.access_token);
    await fetchMe();
  };

  const register = async (email: string, password: string) => {
    const data = await apiFetch<{ access_token: string; user: User }>(
      "/auth/register",
      {
        method: "POST",
        body: JSON.stringify({ email, password }),
      },
      "none",
    );

    setToken(data.access_token);
    await fetchMe();
  };

  const logout = () => {
    clearToken();
    setUser(null);
    setAccount(null);

    if (typeof window !== "undefined") {
      window.location.href = "/login";
    }
  };

  const refreshAccount = async () => {
    await fetchMe();
  };

  return (
    <AuthContext.Provider
      value={{ user, account, isLoading, login, register, logout, refreshAccount }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);

  if (context === undefined) {
    throw new Error("useAuth must be used within an AuthProvider");
  }

  return context;
}
