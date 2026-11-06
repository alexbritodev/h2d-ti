import { useQuery, useQueryClient } from "@tanstack/react-query";
import { CheckCircle2, Crown, Pencil, XCircle } from "lucide-react";
import { type FormEvent, useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { type Column, DataTable } from "@/components/ui/data-table";
import { Input } from "@/components/ui/input";
import { Avatar, Field, Modal, Select, Switch } from "@/components/ui/primitives";
import { toast } from "@/components/ui/toast";
import type { Role } from "@/lib/api/client";
import { meQuery } from "@/lib/auth";

import {
  type AdminUser,
  inviteUser,
  resendInvite,
  resetPassword,
  ROLE_LABELS,
  updateUser,
  usersQuery,
} from "./users";

const PASSWORD_HINT = "Mínimo de 6 caracteres, com letras e números.";

function Status({ active }: { active: boolean }) {
  const Icon = active ? CheckCircle2 : XCircle;
  return (
    <Badge tone={active ? "accent" : "neutral"}>
      <Icon aria-hidden className="size-3" />
      {active ? "Ativo" : "Inativo"}
    </Badge>
  );
}

/** Lista de usuários e os formulários de criar e editar. Fala com a API de verdade. */
export function UsersTab({
  creating,
  onCreatingChange,
}: {
  creating: boolean;
  onCreatingChange: (open: boolean) => void;
}) {
  const queryClient = useQueryClient();
  const { data: users = [], isPending, isError } = useQuery(usersQuery);
  const { data: me } = useQuery(meQuery);
  const [editing, setEditing] = useState<AdminUser | null>(null);

  const refresh = () => queryClient.invalidateQueries({ queryKey: usersQuery.queryKey });

  const columns: Column<AdminUser>[] = [
    {
      key: "name",
      header: "Nome",
      sortValue: (user) => user.name,
      render: (user) => (
        <div className="flex items-center gap-3">
          <Avatar name={user.name} />
          <div>
            <p className="flex items-center gap-1.5 font-medium whitespace-nowrap">
              {user.name}
              {user.is_vip && (
                <Badge tone="warn">
                  <Crown aria-hidden className="size-3" />
                  VIP
                </Badge>
              )}
            </p>
            <p className="font-mono text-[11px] text-muted">{user.email}</p>
          </div>
        </div>
      ),
    },
    {
      key: "role",
      header: "Papel",
      sortValue: (user) => ROLE_LABELS[user.role],
      render: (user) => <Badge>{ROLE_LABELS[user.role]}</Badge>,
    },
    {
      key: "department",
      header: "Setor",
      sortValue: (user) => user.department ?? "",
      render: (user) => user.department ?? "—",
    },
    {
      key: "active",
      header: "Situação",
      render: (user) =>
        user.is_active && user.invite_pending ? (
          <Badge tone="warn">Convite pendente</Badge>
        ) : (
          <Status active={user.is_active} />
        ),
    },
    {
      key: "edit",
      header: "",
      render: (user) => (
        <Button aria-label={`Editar ${user.name}`} onClick={() => setEditing(user)}>
          <Pencil aria-hidden className="size-4" />
        </Button>
      ),
    },
  ];

  if (isPending) return <p className="p-4 text-sm text-muted">Carregando usuários…</p>;
  if (isError)
    return (
      <p role="alert" className="p-4 text-sm text-danger">
        Não foi possível carregar os usuários.
      </p>
    );

  return (
    <>
      <div className="-mx-4">
        <DataTable
          label="Usuários"
          columns={columns}
          rows={users}
          rowKey={(user) => user.id}
          pageSize={8}
          onRowClick={setEditing}
        />
      </div>

      <CreateModal
        open={creating}
        onOpenChange={onCreatingChange}
        onDone={() => {
          onCreatingChange(false);
          void refresh();
        }}
      />
      <EditModal
        // A chave refaz o formulário a cada pessoa, sem sobrar valor da anterior.
        key={editing?.id ?? "none"}
        user={editing}
        isSelf={editing?.id === me?.id}
        onClose={() => setEditing(null)}
        onDone={() => {
          setEditing(null);
          void refresh();
        }}
      />
    </>
  );
}

function RoleOptions() {
  return (
    <>
      {(Object.keys(ROLE_LABELS) as Role[]).map((role) => (
        <option key={role} value={role}>
          {ROLE_LABELS[role]}
        </option>
      ))}
    </>
  );
}

function CreateModal({
  open,
  onOpenChange,
  onDone,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onDone: () => void;
}) {
  const [error, setError] = useState<string | null>(null);
  const [vip, setVip] = useState(false);
  const [busy, setBusy] = useState(false);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    setBusy(true);
    setError(null);
    const result = await inviteUser({
      name: String(form.get("name") ?? ""),
      email: String(form.get("email") ?? ""),
      role: String(form.get("role")) as Role,
      department: String(form.get("department") ?? "") || null,
      is_vip: vip,
    });
    setBusy(false);
    if (!result.ok) return setError(result.message);
    toast("Convite enviado", `${result.data.email} recebe o link para definir a senha.`);
    setVip(false);
    onDone();
  }

  return (
    <Modal
      open={open}
      onOpenChange={(next) => {
        if (!next) setError(null);
        onOpenChange(next);
      }}
      title="Convidar usuário"
      footer={
        <>
          <Button onClick={() => onOpenChange(false)}>Cancelar</Button>
          <Button variant="primary" type="submit" form="new-user" disabled={busy}>
            {busy ? "Enviando…" : "Enviar convite"}
          </Button>
        </>
      }
    >
      <form id="new-user" onSubmit={submit} className="space-y-4">
        <Field label="Nome" htmlFor="new-user-name">
          <Input id="new-user-name" name="name" required maxLength={200} />
        </Field>
        <Field label="E-mail" htmlFor="new-user-email">
          <Input id="new-user-email" name="email" type="email" required autoComplete="off" />
        </Field>
        <p className="rounded-lg bg-surface-2 p-3 text-sm text-muted">
          A pessoa recebe um e-mail com um link para definir a própria senha. O link vale por 48 horas.
        </p>
        <Field label="Papel" htmlFor="new-user-role">
          <Select id="new-user-role" name="role" defaultValue="user">
            <RoleOptions />
          </Select>
        </Field>
        <Field label="Setor" htmlFor="new-user-department" hint="Opcional">
          <Input id="new-user-department" name="department" maxLength={120} />
        </Field>
        <div className="flex items-center justify-between">
          <label htmlFor="new-user-vip" className="font-medium">
            Usuário VIP
          </label>
          <Switch id="new-user-vip" label="Usuário VIP" checked={vip} onCheckedChange={setVip} />
        </div>
        {error && (
          <p role="alert" className="text-sm text-danger">
            {error}
          </p>
        )}
      </form>
    </Modal>
  );
}

function EditModal({
  user,
  isSelf,
  onClose,
  onDone,
}: {
  user: AdminUser | null;
  isSelf: boolean;
  onClose: () => void;
  onDone: () => void;
}) {
  const [error, setError] = useState<string | null>(null);
  const [vip, setVip] = useState(user?.is_vip ?? false);
  const [active, setActive] = useState(user?.is_active ?? true);
  const [busy, setBusy] = useState(false);

  async function save(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!user) return;
    const form = new FormData(event.currentTarget);
    setBusy(true);
    setError(null);
    const result = await updateUser(user.id, {
      name: String(form.get("name") ?? ""),
      role: String(form.get("role")) as Role,
      department: String(form.get("department") ?? "") || null,
      is_vip: vip,
      is_active: active,
    });
    setBusy(false);
    if (!result.ok) return setError(result.message);
    toast("Usuário atualizado", user.email);
    onDone();
  }

  async function sendLink() {
    if (!user) return;
    setBusy(true);
    setError(null);
    const result = await resendInvite(user.id);
    setBusy(false);
    if (!result.ok) return setError(result.message);
    toast("Link enviado", `${user.email} recebe um novo link (o anterior deixa de valer).`);
    onDone();
  }

  async function reset(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!user) return;
    const input = event.currentTarget.elements.namedItem("new-password") as HTMLInputElement;
    setBusy(true);
    setError(null);
    const result = await resetPassword(user.id, input.value);
    setBusy(false);
    if (!result.ok) return setError(result.message);
    input.value = "";
    toast("Senha redefinida", `Avise ${user.name} da nova senha.`);
  }

  return (
    <Modal
      open={user !== null}
      onOpenChange={(open) => !open && onClose()}
      title={user ? `Editar: ${user.name}` : "Editar usuário"}
      description={user?.email}
      footer={
        <>
          <Button onClick={onClose}>Cancelar</Button>
          <Button variant="primary" type="submit" form="edit-user" disabled={busy}>
            {busy ? "Salvando…" : "Salvar"}
          </Button>
        </>
      }
    >
      {user && (
        <div className="space-y-6">
          <form id="edit-user" onSubmit={save} className="space-y-4">
            <Field label="Nome" htmlFor="edit-user-name">
              <Input id="edit-user-name" name="name" required maxLength={200} defaultValue={user.name} />
            </Field>
            <Field
              label="Papel"
              htmlFor="edit-user-role"
              hint={isSelf ? "Você não pode mudar o seu próprio papel." : undefined}
            >
              <Select id="edit-user-role" name="role" defaultValue={user.role} disabled={isSelf}>
                <RoleOptions />
              </Select>
            </Field>
            <Field label="Setor" htmlFor="edit-user-department" hint="Opcional">
              <Input id="edit-user-department" name="department" maxLength={120} defaultValue={user.department ?? ""} />
            </Field>
            <div className="flex items-center justify-between">
              <label htmlFor="edit-user-vip" className="font-medium">
                Usuário VIP
              </label>
              <Switch id="edit-user-vip" label="Usuário VIP" checked={vip} onCheckedChange={setVip} />
            </div>
            <div className="flex items-center justify-between">
              <label htmlFor="edit-user-active" className="font-medium">
                Conta ativa
              </label>
              <Switch
                id="edit-user-active"
                label="Conta ativa"
                checked={active}
                onCheckedChange={setActive}
                disabled={isSelf}
              />
            </div>
          </form>

          <div className="space-y-2 border-t border-border pt-4">
            <p className="font-medium">Link de acesso por e-mail</p>
            <p className="text-xs text-muted">
              Para quem ainda não entrou ou esqueceu a senha. O link vale por 48 horas e só funciona
              uma vez.
            </p>
            <Button onClick={sendLink} disabled={busy || !user.is_active}>
              Enviar novo link
            </Button>
          </div>

          <form onSubmit={reset} className="space-y-3 border-t border-border pt-4">
            <Field label="Redefinir senha" htmlFor="edit-user-password" hint={PASSWORD_HINT}>
              <div className="flex gap-2">
                <Input
                  id="edit-user-password"
                  name="new-password"
                  type="text"
                  required
                  minLength={6}
                  autoComplete="off"
                  placeholder="Nova senha"
                />
                <Button type="submit" disabled={busy}>
                  Redefinir
                </Button>
              </div>
            </Field>
          </form>

          {error && (
            <p role="alert" className="text-sm text-danger">
              {error}
            </p>
          )}
        </div>
      )}
    </Modal>
  );
}
