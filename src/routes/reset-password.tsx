import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { useEffect, useState, type FormEvent } from "react";
import { z } from "zod";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Button } from "@/components/ui/button";
import { toast } from "sonner";
import { supabase } from "@/integrations/supabase/client";
import { Loader2 } from "lucide-react";

export const Route = createFileRoute("/reset-password")({
  head: () => ({
    meta: [
      { title: "Redefinir senha — Compra Certa Marília" },
      { name: "description", content: "Escolha uma nova senha para sua conta." },
      { name: "robots", content: "noindex" },
    ],
  }),
  component: ResetPasswordPage,
});

const schema = z.object({
  password: z.string().min(6, "A senha deve ter pelo menos 6 caracteres").max(128),
});

function ResetPasswordPage() {
  const navigate = useNavigate();
  const [ready, setReady] = useState(false);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    // Supabase parses the recovery token from the URL hash and fires PASSWORD_RECOVERY.
    const { data: sub } = supabase.auth.onAuthStateChange((event) => {
      if (event === "PASSWORD_RECOVERY" || event === "SIGNED_IN") setReady(true);
    });
    supabase.auth.getSession().then(({ data }) => {
      if (data.session) setReady(true);
    });
    return () => sub.subscription.unsubscribe();
  }, []);

  async function onSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const form = new FormData(e.currentTarget);
    const parsed = schema.safeParse({ password: form.get("password") });
    if (!parsed.success) {
      toast.error(parsed.error.issues[0]?.message ?? "Senha inválida");
      return;
    }
    setLoading(true);
    const { error } = await supabase.auth.updateUser({ password: parsed.data.password });
    setLoading(false);
    if (error) {
      toast.error(error.message);
      return;
    }
    toast.success("Senha atualizada!");
    navigate({ to: "/", replace: true });
  }

  return (
    <div className="mx-auto max-w-md px-4 py-8 md:py-14">
      <h1 className="text-2xl font-bold">Redefinir senha</h1>
      <p className="mt-1 text-sm text-muted-foreground">
        Escolha uma nova senha para sua conta.
      </p>

      {!ready ? (
        <p className="mt-6 text-sm text-muted-foreground">
          Abra este link a partir do e-mail de recuperação para redefinir sua senha.
        </p>
      ) : (
        <form onSubmit={onSubmit} className="mt-6 space-y-4">
          <div className="space-y-2">
            <Label htmlFor="new-password">Nova senha</Label>
            <Input
              id="new-password"
              name="password"
              type="password"
              autoComplete="new-password"
              minLength={6}
              required
            />
          </div>
          <Button className="w-full" disabled={loading}>
            {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : "Salvar nova senha"}
          </Button>
        </form>
      )}
    </div>
  );
}
