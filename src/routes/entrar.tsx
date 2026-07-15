import { createFileRoute } from "@tanstack/react-router";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Button } from "@/components/ui/button";

export const Route = createFileRoute("/entrar")({
  head: () => ({
    meta: [
      { title: "Entrar ou cadastrar — Compra Certa Marília" },
      { name: "description", content: "Acesse sua conta ou crie uma para salvar suas listas de compras." },
      { property: "og:title", content: "Entrar ou cadastrar — Compra Certa Marília" },
      { property: "og:description", content: "Acesse sua conta ou crie uma para salvar suas listas de compras." },
    ],
  }),
  component: EntrarPage,
});

function EntrarPage() {
  return (
    <div className="mx-auto max-w-md px-4 py-8 md:py-14">
      <h1 className="text-center text-2xl font-bold">Bem-vindo</h1>
      <p className="mt-1 text-center text-sm text-muted-foreground">
        Entre na sua conta ou crie uma nova.
      </p>

      <Tabs defaultValue="login" className="mt-6">
        <TabsList className="grid w-full grid-cols-2">
          <TabsTrigger value="login">Entrar</TabsTrigger>
          <TabsTrigger value="signup">Cadastrar</TabsTrigger>
        </TabsList>

        <TabsContent value="login" className="mt-6 space-y-4">
          <div className="space-y-2">
            <Label htmlFor="login-email">E-mail</Label>
            <Input id="login-email" type="email" autoComplete="email" />
          </div>
          <div className="space-y-2">
            <Label htmlFor="login-pass">Senha</Label>
            <Input id="login-pass" type="password" autoComplete="current-password" />
          </div>
          <Button className="w-full">Entrar</Button>
        </TabsContent>

        <TabsContent value="signup" className="mt-6 space-y-4">
          <div className="space-y-2">
            <Label htmlFor="signup-name">Nome</Label>
            <Input id="signup-name" autoComplete="name" />
          </div>
          <div className="space-y-2">
            <Label htmlFor="signup-email">E-mail</Label>
            <Input id="signup-email" type="email" autoComplete="email" />
          </div>
          <div className="space-y-2">
            <Label htmlFor="signup-pass">Senha</Label>
            <Input id="signup-pass" type="password" autoComplete="new-password" />
          </div>
          <Button className="w-full">Criar conta</Button>
        </TabsContent>
      </Tabs>
    </div>
  );
}
