import {
  createContext,
  type ReactNode,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState
} from "react";
import { AlertCircle, CheckCircle2, Info, X } from "lucide-react";

import { cn } from "../../lib/utils";
import { Button } from "./button";

type NotificationTone = "info" | "success" | "error";

interface NotificationInput {
  title: string;
  description?: string;
  tone?: NotificationTone;
  durationMs?: number;
}

interface NotificationRecord extends Required<Pick<NotificationInput, "title" | "tone" | "durationMs">> {
  id: number;
  description?: string;
}

interface NotificationContextValue {
  notify: (input: NotificationInput) => void;
  dismiss: (id: number) => void;
}

const DEFAULT_NOTIFICATION_DURATION_MS = 4200;

const NotificationContext = createContext<NotificationContextValue | null>(null);

function toneIcon(tone: NotificationTone) {
  switch (tone) {
    case "success":
      return CheckCircle2;
    case "error":
      return AlertCircle;
    default:
      return Info;
  }
}

export function NotificationProvider({ children }: { children: ReactNode }) {
  const [notifications, setNotifications] = useState<NotificationRecord[]>([]);
  const nextIdRef = useRef(1);
  const timeoutIdsRef = useRef<Map<number, number>>(new Map());

  const dismiss = useCallback((id: number) => {
    const timeoutId = timeoutIdsRef.current.get(id);
    if (timeoutId !== undefined) {
      window.clearTimeout(timeoutId);
      timeoutIdsRef.current.delete(id);
    }
    setNotifications((current) => current.filter((notification) => notification.id !== id));
  }, []);

  const notify = useCallback(
    (input: NotificationInput) => {
      const id = nextIdRef.current;
      nextIdRef.current += 1;

      const notification: NotificationRecord = {
        id,
        title: input.title,
        description: input.description,
        tone: input.tone ?? "info",
        durationMs: input.durationMs ?? DEFAULT_NOTIFICATION_DURATION_MS
      };

      setNotifications((current) => [...current, notification]);
      const timeoutId = window.setTimeout(() => {
        dismiss(id);
      }, notification.durationMs);
      timeoutIdsRef.current.set(id, timeoutId);
    },
    [dismiss]
  );

  useEffect(() => {
    return () => {
      timeoutIdsRef.current.forEach((timeoutId) => {
        window.clearTimeout(timeoutId);
      });
      timeoutIdsRef.current.clear();
    };
  }, []);

  const value = useMemo(
    () => ({
      notify,
      dismiss
    }),
    [dismiss, notify]
  );

  return (
    <NotificationContext.Provider value={value}>
      {children}
      <div className="notification-viewport" aria-live="polite" aria-atomic="false">
        {notifications.map((notification) => {
          const Icon = toneIcon(notification.tone);
          return (
            <section
              key={notification.id}
              className={cn("notification-toast", `notification-toast-${notification.tone}`)}
              role={notification.tone === "error" ? "alert" : "status"}
            >
              <div className="notification-toast-icon">
                <Icon className="h-4 w-4" aria-hidden="true" />
              </div>
              <div className="notification-toast-copy">
                <p className="notification-toast-title">{notification.title}</p>
                {notification.description ? <p className="notification-toast-description">{notification.description}</p> : null}
              </div>
              <Button
                type="button"
                variant="ghost"
                size="icon"
                className="notification-toast-dismiss"
                onClick={() => dismiss(notification.id)}
                aria-label={`Dismiss notification ${notification.title}`}
              >
                <X className="h-3.5 w-3.5" aria-hidden="true" />
              </Button>
            </section>
          );
        })}
      </div>
    </NotificationContext.Provider>
  );
}

export function useNotifications(): NotificationContextValue {
  const value = useContext(NotificationContext);
  if (!value) {
    throw new Error("useNotifications must be used within a NotificationProvider.");
  }
  return value;
}
