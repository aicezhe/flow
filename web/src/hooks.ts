import { useCallback, useEffect, useRef, useState } from "react";

export interface LoadState<T> {
  data: T | null;
  error: string | null;
  loading: boolean;
  reload: () => void;
}

export function errText(e: unknown): string {
  return e instanceof Error ? e.message : "Неизвестная ошибка";
}

// Загружает данные при появлении компонента; reload() обновляет их.
// Счётчик seq отбрасывает ответы устаревших запросов.
export function useLoad<T>(loader: () => Promise<T>): LoadState<T> {
  const [state, setState] = useState<Omit<LoadState<T>, "reload">>({
    data: null,
    error: null,
    loading: true,
  });
  const loaderRef = useRef(loader);
  loaderRef.current = loader;
  const seq = useRef(0);

  const reload = useCallback(() => {
    const id = ++seq.current;
    setState((s) => ({ ...s, loading: true, error: null }));
    loaderRef
      .current()
      .then((data) => {
        if (id === seq.current) setState({ data, error: null, loading: false });
      })
      .catch((e: unknown) => {
        if (id === seq.current) setState((s) => ({ ...s, error: errText(e), loading: false }));
      });
  }, []);

  useEffect(() => {
    reload();
    return () => {
      seq.current++;
    };
  }, [reload]);

  return { ...state, reload };
}
