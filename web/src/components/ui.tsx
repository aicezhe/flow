import type { ReactNode } from "react";
import type { LoadState } from "../hooks";

export function Loading({ text = "Загружаем…" }: { text?: string }) {
  return (
    <p className="state" role="status">
      <span className="spinner" aria-hidden="true" /> {text}
    </p>
  );
}

export function Empty({ title, children }: { title: string; children?: ReactNode }) {
  return (
    <div className="state empty">
      <h3>{title}</h3>
      {children && <p>{children}</p>}
    </div>
  );
}

export function ErrorBox({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return (
    <div className="state error" role="alert">
      <p>{message}</p>
      {onRetry && (
        <button type="button" className="btn small" onClick={onRetry}>
          Повторить
        </button>
      )}
    </div>
  );
}

// Единое поведение для загрузки / ошибки / пусто / данные.
export function Async<T>(props: {
  state: LoadState<T>;
  isEmpty?: (data: T) => boolean;
  empty: ReactNode;
  children: (data: T) => ReactNode;
}) {
  const { state, isEmpty, empty, children } = props;
  if (state.data === null) {
    return state.error ? <ErrorBox message={state.error} onRetry={state.reload} /> : <Loading />;
  }
  return (
    <>
      {state.error && <ErrorBox message={state.error} onRetry={state.reload} />}
      {isEmpty?.(state.data) ? empty : children(state.data)}
    </>
  );
}
