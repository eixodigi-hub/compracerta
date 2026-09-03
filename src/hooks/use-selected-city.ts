import { useEffect, useState } from "react";

const STORAGE_KEY = "compra-certa:selected-city";
const CHANGE_EVENT = "compra-certa:selected-city-change";

/**
 * `undefined` = ainda não verificamos o localStorage (SSR / primeiro
 * paint no cliente) — nunca deve abrir o gate nesse estado, senão pisca
 * para todo mundo antes da hidratação. `null` = verificado, nenhuma
 * cidade escolhida ainda.
 *
 * Vários componentes (TopNav, CitySelectGate) usam este hook ao mesmo
 * tempo; cada um mantém seu próprio estado local, mas todos escutam o
 * evento customizado disparado por selectCity/clearCity para ficarem em
 * sincronia sem precisar de um Context Provider.
 */
export function useSelectedCity() {
  const [citySlug, setCitySlugState] = useState<string | null | undefined>(undefined);

  useEffect(() => {
    const readStored = (): string | null => {
      try {
        return window.localStorage.getItem(STORAGE_KEY);
      } catch {
        return null;
      }
    };

    setCitySlugState(readStored());

    const onChange = () => setCitySlugState(readStored());
    window.addEventListener(CHANGE_EVENT, onChange);
    window.addEventListener("storage", onChange);
    return () => {
      window.removeEventListener(CHANGE_EVENT, onChange);
      window.removeEventListener("storage", onChange);
    };
  }, []);

  function selectCity(slug: string) {
    try {
      window.localStorage.setItem(STORAGE_KEY, slug);
    } catch {
      // localStorage indisponível (modo privado etc.) — segue só em memória.
    }
    setCitySlugState(slug);
    window.dispatchEvent(new Event(CHANGE_EVENT));
  }

  function clearCity() {
    try {
      window.localStorage.removeItem(STORAGE_KEY);
    } catch {
      // ignorado
    }
    setCitySlugState(null);
    window.dispatchEvent(new Event(CHANGE_EVENT));
  }

  return { citySlug, selectCity, clearCity };
}
