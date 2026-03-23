"use client";

import { FormEvent, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { toast } from "sonner";

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useAuth } from "@/contexts/auth-context";
import { apiFetch } from "@/lib/api";

export default function OnboardingPage() {
  const { user, account, isLoading, refreshAccount } = useAuth();
  const router = useRouter();
  const [companyName, setCompanyName] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  useEffect(() => {
    if (!isLoading && !user) {
      router.replace("/login");
    }

    if (!isLoading && user && account?.company_name) {
      router.replace("/dashboard");
    }
  }, [account, isLoading, router, user]);

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setError(null);
    setIsSubmitting(true);

    try {
      await apiFetch<{ account: { company_name: string | null } }>(
        "/auth/account",
        {
          method: "PATCH",
          body: JSON.stringify({ company_name: companyName }),
        },
      );

      await refreshAccount();
      toast.success("Company details saved");
      router.replace("/imports/new");
    } catch (submitError) {
      const message =
        submitError instanceof Error
          ? submitError.message
          : "Unable to save company details.";
      setError(message);
      toast.error(message);
    } finally {
      setIsSubmitting(false);
    }
  };

  if (isLoading || !user) {
    return (
      <main className="flex min-h-screen items-center justify-center bg-muted/20">
        <p className="text-sm text-muted-foreground">Loading...</p>
      </main>
    );
  }

  return (
    <main className="flex min-h-screen items-center justify-center bg-[linear-gradient(180deg,_#ffffff_0%,_#eef6ff_100%)] px-6 py-12">
      <Card className="w-full max-w-lg border-border/80 bg-background/95 shadow-lg">
        <CardHeader className="space-y-2">
          <CardTitle className="text-2xl">Finish onboarding</CardTitle>
          <CardDescription>
            Add your company name so we can route you into the import flow.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-6">
          <form className="space-y-4" onSubmit={handleSubmit}>
            <div className="space-y-2">
              <Label htmlFor="company-name">Company name</Label>
              <Input
                id="company-name"
                value={companyName}
                onChange={(event) => setCompanyName(event.target.value)}
                placeholder="Acme s.r.o."
                required
              />
            </div>

            {error ? (
              <Alert variant="destructive">
                <AlertTitle>Could not save onboarding</AlertTitle>
                <AlertDescription>{error}</AlertDescription>
              </Alert>
            ) : null}

            <Button
              type="submit"
              size="lg"
              className="w-full"
              disabled={isSubmitting}
            >
              {isSubmitting ? "Saving..." : "Continue to imports"}
            </Button>
          </form>
        </CardContent>
      </Card>
    </main>
  );
}
