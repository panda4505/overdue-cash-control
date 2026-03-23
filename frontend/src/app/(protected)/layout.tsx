"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect } from "react";

import { Button } from "@/components/ui/button";
import { useAuth } from "@/contexts/auth-context";
import { cn } from "@/lib/utils";

export default function ProtectedLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const { user, account, isLoading, logout } = useAuth();
  const router = useRouter();
  const pathname = usePathname();

  useEffect(() => {
    if (!isLoading && !user) {
      router.replace("/login");
    }

    if (!isLoading && user && account?.company_name === null && pathname !== "/onboarding") {
      router.replace("/onboarding");
    }
  }, [account, isLoading, pathname, router, user]);

  if (isLoading || !user) {
    return (
      <div className="flex h-screen items-center justify-center">
        <p className="text-sm text-muted-foreground">Loading...</p>
      </div>
    );
  }

  return (
    <div className="flex min-h-screen bg-muted/20">
      <aside className="hidden w-72 border-r bg-background/95 p-6 md:flex md:flex-col">
        <div className="mb-8 space-y-1">
          <p className="text-xs font-medium uppercase tracking-[0.22em] text-muted-foreground">
            Overdue Cash Control
          </p>
          <p className="text-lg font-semibold text-foreground">Workspace</p>
        </div>

        <nav className="flex flex-col gap-2">
          <Link
            href="/dashboard"
            className={cn(
              "rounded-lg px-3 py-2 text-sm transition-colors",
              pathname === "/dashboard"
                ? "bg-muted font-medium text-foreground"
                : "text-muted-foreground hover:bg-muted hover:text-foreground",
            )}
          >
            Dashboard
          </Link>
          <Link
            href="/imports/new"
            className={cn(
              "rounded-lg px-3 py-2 text-sm transition-colors",
              pathname === "/imports/new"
                ? "bg-muted font-medium text-foreground"
                : "text-muted-foreground hover:bg-muted hover:text-foreground",
            )}
          >
            New Import
          </Link>
        </nav>

        <div className="mt-auto space-y-3 border-t pt-4">
          <div className="space-y-1">
            <p className="text-sm font-medium text-foreground">{user.email}</p>
            <p className="text-xs text-muted-foreground">
              {account?.company_name ?? "Company setup pending"}
            </p>
          </div>
          <Button variant="ghost" className="justify-start px-0" onClick={logout}>
            Sign out
          </Button>
        </div>
      </aside>

      <main className="flex-1 overflow-auto p-6 md:p-8">{children}</main>
    </div>
  );
}
