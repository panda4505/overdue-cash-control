"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect } from "react";
import { ArrowRight, ShieldCheck, UploadCloud } from "lucide-react";

import { buttonVariants } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { useAuth } from "@/contexts/auth-context";
import { cn } from "@/lib/utils";

export default function Home() {
  const { user, account, isLoading } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (!isLoading && user) {
      router.replace(account?.company_name ? "/dashboard" : "/onboarding");
    }
  }, [account, isLoading, router, user]);

  if (isLoading || user) {
    return (
      <main className="flex min-h-screen items-center justify-center bg-background">
        <p className="text-sm text-muted-foreground">Loading...</p>
      </main>
    );
  }

  return (
    <main className="min-h-screen bg-[radial-gradient(circle_at_top,_rgba(15,23,42,0.07),_transparent_45%),linear-gradient(180deg,_#ffffff_0%,_#f6f7fb_100%)] px-6 py-12">
      <div className="mx-auto flex max-w-6xl flex-col gap-12 lg:flex-row lg:items-center">
        <section className="max-w-2xl space-y-6">
          <div className="inline-flex rounded-full border border-border bg-background/80 px-3 py-1 text-xs font-medium uppercase tracking-[0.24em] text-muted-foreground shadow-sm">
            Overdue Cash Control
          </div>
          <div className="space-y-4">
            <h1 className="max-w-xl text-4xl font-semibold tracking-tight text-foreground sm:text-5xl">
              Bring invoice exports into a clean collections workflow.
            </h1>
            <p className="max-w-xl text-base leading-7 text-muted-foreground sm:text-lg">
              Authenticate, finish onboarding, upload a receivables file, review
              the suggested mapping, and confirm the import in one guided flow.
            </p>
          </div>
          <div className="flex flex-col gap-3 sm:flex-row">
            <Link
              href="/login"
              className={cn(buttonVariants({ size: "lg" }), "justify-center")}
            >
              Login
            </Link>
            <Link
              href="/register"
              className={cn(
                buttonVariants({ variant: "outline", size: "lg" }),
                "justify-center",
              )}
            >
              Register
              <ArrowRight className="size-4" />
            </Link>
          </div>
        </section>

        <section className="grid flex-1 gap-4 md:grid-cols-2">
          <Card className="border-border/80 bg-background/90 shadow-sm">
            <CardHeader>
              <UploadCloud className="size-5 text-foreground" />
              <CardTitle>Import Preview</CardTitle>
              <CardDescription>
                Upload CSV, TSV, or XLSX files and confirm how each column maps
                before anything is committed.
              </CardDescription>
            </CardHeader>
            <CardContent className="text-sm leading-6 text-muted-foreground">
              Review inferred headers, resolve fuzzy customer matches, and save
              the mapping as a reusable template when it looks right.
            </CardContent>
          </Card>
          <Card className="border-border/80 bg-background/90 shadow-sm">
            <CardHeader>
              <ShieldCheck className="size-5 text-foreground" />
              <CardTitle>Client-Side Session</CardTitle>
              <CardDescription>
                Sign in quickly, keep routing simple, and let the app redirect
                you into onboarding or the dashboard automatically.
              </CardDescription>
            </CardHeader>
            <CardContent className="text-sm leading-6 text-muted-foreground">
              The auth flow is built around the backend contracts already in the
              repo, with resilient account refreshes and clear error handling.
            </CardContent>
          </Card>
        </section>
      </div>
    </main>
  );
}
