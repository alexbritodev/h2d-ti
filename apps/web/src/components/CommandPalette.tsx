import { useQuery } from "@tanstack/react-query";
import { useNavigate } from "@tanstack/react-router";
import { Command } from "cmdk";
import { Search, Ticket as TicketIcon } from "lucide-react";
import { Dialog } from "radix-ui";

import type { Role } from "@/lib/api/client";
import { ticketsQuery } from "@/features/tickets/api";
import { navItemsFor } from "@/lib/navigation";

const ITEM_CLASS =
  "flex h-10 cursor-pointer items-center gap-3 rounded-lg px-3 aria-selected:bg-surface-2";
const GROUP_CLASS =
  "mb-2 [&_[cmdk-group-heading]]:px-3 [&_[cmdk-group-heading]]:py-1.5 [&_[cmdk-group-heading]]:text-xs [&_[cmdk-group-heading]]:text-muted";

export function CommandPalette({
  open,
  onOpenChange,
  role,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  role: Role;
}) {
  const navigate = useNavigate();
  const canSeeQueue = role !== "user";
  const { data: tickets = [] } = useQuery({ ...ticketsQuery(), enabled: open && canSeeQueue });

  function go(path: string) {
    onOpenChange(false);
    void navigate({ to: path });
  }

  return (
    <Dialog.Root open={open} onOpenChange={onOpenChange}>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 z-40 bg-black/50" />
        <Dialog.Content className="fixed top-[12vh] left-1/2 z-50 w-[calc(100vw-2rem)] max-w-xl -translate-x-1/2 overflow-hidden rounded-xl border border-border bg-surface shadow-card">
          <Dialog.Title className="sr-only">Buscar no sistema</Dialog.Title>
          <Dialog.Description className="sr-only">
            Encontre módulos e chamados pelo nome ou pelo código.
          </Dialog.Description>
          <Command label="Buscar no sistema">
            <div className="flex items-center gap-3 border-b border-border px-4">
              <Search aria-hidden className="size-[18px] text-muted" />
              <Command.Input
                placeholder="Buscar módulos e chamados..."
                className="h-12 w-full bg-transparent text-sm outline-none placeholder:text-muted"
              />
            </div>
            <Command.List className="max-h-80 overflow-y-auto p-2">
              <Command.Empty className="py-8 text-center text-muted">
                Nada encontrado.
              </Command.Empty>
              <Command.Group heading="Módulos" className={GROUP_CLASS}>
                {navItemsFor(role).map((item) => (
                  <Command.Item
                    key={item.path}
                    value={item.title}
                    onSelect={() => go(item.path)}
                    className={ITEM_CLASS}
                  >
                    <item.icon aria-hidden className="size-4 text-muted" />
                    {item.title}
                  </Command.Item>
                ))}
              </Command.Group>
              {canSeeQueue && (
                <Command.Group heading="Chamados" className={GROUP_CLASS}>
                  {tickets.map((ticket) => (
                    <Command.Item
                      key={ticket.id}
                      value={`${ticket.code} ${ticket.summary}`}
                      onSelect={() => go("/chamados")}
                      className={ITEM_CLASS}
                    >
                      <TicketIcon aria-hidden className="size-4 shrink-0 text-muted" />
                      <span className="shrink-0 font-mono text-xs text-muted">{ticket.code}</span>
                      <span className="truncate">{ticket.summary}</span>
                    </Command.Item>
                  ))}
                </Command.Group>
              )}
            </Command.List>
          </Command>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
