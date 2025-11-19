import AsyncStorage from "@react-native-async-storage/async-storage";
import {
  createContext,
  PropsWithChildren,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from "react";
import { Config } from "../config";

type ServerState = {
  baseUrl: string;
  uploadKey: string | null;
  lastConnected: string | null;
};

type ServerContextValue = ServerState & {
  setBaseUrl: (next: string) => void;
  setUploadKey: (next: string | null) => void;
  setLastConnected: (value: string | null) => void;
  hydrated: boolean;
};

const STORAGE_KEY = "@fliplens/server-settings";
const DEFAULT_STATE: ServerState = {
  baseUrl: Config.apiBase,
  uploadKey: null,
  lastConnected: null,
};

const ServerContext = createContext<ServerContextValue | undefined>(undefined);

export const ServerProvider = ({ children }: PropsWithChildren) => {
  const [state, setState] = useState<ServerState>(DEFAULT_STATE);
  const [hydrated, setHydrated] = useState(false);

  useEffect(() => {
    (async () => {
      try {
        const raw = await AsyncStorage.getItem(STORAGE_KEY);
        if (raw) {
          const parsed = JSON.parse(raw);
          setState({
            baseUrl: parsed.baseUrl || Config.apiBase,
            uploadKey: parsed.uploadKey || null,
            lastConnected: parsed.lastConnected || null,
          });
        }
      } catch (error) {
        console.warn("server_state_restore_failed", error);
      } finally {
        setHydrated(true);
      }
    })();
  }, []);

  const persist = useCallback(async (next: ServerState) => {
    try {
      await AsyncStorage.setItem(STORAGE_KEY, JSON.stringify(next));
    } catch (error) {
      console.warn("server_state_persist_failed", error);
    }
  }, []);

  const updateState = useCallback(
    (patch: Partial<ServerState>) => {
      setState((prev) => {
        const next = { ...prev, ...patch };
        persist(next);
        return next;
      });
    },
    [persist]
  );

  const value = useMemo<ServerContextValue>(
    () => ({
      baseUrl: state.baseUrl,
      uploadKey: state.uploadKey,
      lastConnected: state.lastConnected,
      hydrated,
      setBaseUrl: (next: string) =>
        updateState({ baseUrl: next.trim() || Config.apiBase }),
      setUploadKey: (next: string | null) =>
        updateState({ uploadKey: next?.trim() || null }),
      setLastConnected: (value: string | null) =>
        updateState({ lastConnected: value }),
    }),
    [hydrated, state.baseUrl, state.lastConnected, state.uploadKey, updateState]
  );

  return (
    <ServerContext.Provider value={value}>{children}</ServerContext.Provider>
  );
};

export function useServer(): ServerContextValue {
  const ctx = useContext(ServerContext);
  if (!ctx) {
    throw new Error("useServer must be used within a ServerProvider");
  }
  return ctx;
}
