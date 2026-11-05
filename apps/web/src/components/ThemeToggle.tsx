import { Moon, Sun } from "lucide-react";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { applyTheme, getStoredTheme, type Theme } from "@/lib/theme";

export function ThemeToggle() {
  const [theme, setTheme] = useState<Theme>(getStoredTheme);
  const next = theme === "dark" ? "light" : "dark";
  const label = next === "dark" ? "Usar tema escuro" : "Usar tema claro";
  const Icon = next === "dark" ? Moon : Sun;

  return (
    <Button
      aria-label={label}
      title={label}
      className="size-10 px-0"
      onClick={() => {
        applyTheme(next);
        setTheme(next);
      }}
    >
      <Icon aria-hidden className="size-[18px]" />
    </Button>
  );
}
