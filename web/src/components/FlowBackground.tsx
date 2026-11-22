import { useEffect, useMemo, useState } from "react";

// Фон «поток»: несколько тонких плавных линий медленно плывут по экрану.
// Каждая линия это отдельный SVG-элемент: браузер рисует его один раз и двигает готовый
// слой на GPU (transform), поэтому основной поток почти не нагружается.
// Линия периодическая (целое число периодов на «плитке»), плитка повторена дважды,
// и сдвиг на -50% ширины замыкается без шва.

const TILE_W = 1200; // ширина одной плитки в единицах viewBox
const H = 200;
const STEPS = 160; // отрезков на плитку: достаточно, чтобы изгибы выглядели гладкими

interface LineSpec {
  top: number; // % высоты экрана
  height: number; // vh
  n1: number; // целое число периодов, главная волна
  a1: number;
  p1: number;
  n2: number; // более мелкая волна
  a2: number;
  p2: number;
  duration: number; // секунд на полный сдвиг: чем больше, тем медленнее
  delay: number; // отрицательная: линии стартуют уже в разных фазах
  reverse: boolean;
  opacity: number;
  color: string;
}

const LINES: LineSpec[] = [
  { top: 6, height: 26, n1: 1, a1: 0.32, p1: 0.4, n2: 3, a2: 0.1, p2: 1.2, duration: 140, delay: -30, reverse: false, opacity: 0.14, color: "var(--blue)" },
  { top: 22, height: 30, n1: 2, a1: 0.28, p1: 2.1, n2: 5, a2: 0.07, p2: 0.3, duration: 105, delay: -70, reverse: true, opacity: 0.1, color: "var(--blue2)" },
  { top: 38, height: 28, n1: 1, a1: 0.36, p1: 4.0, n2: 4, a2: 0.09, p2: 2.6, duration: 160, delay: -90, reverse: false, opacity: 0.16, color: "var(--blue)" },
  { top: 54, height: 30, n1: 3, a1: 0.22, p1: 0.9, n2: 6, a2: 0.06, p2: 3.3, duration: 120, delay: -20, reverse: true, opacity: 0.1, color: "var(--blue2)" },
  { top: 68, height: 26, n1: 2, a1: 0.3, p1: 3.2, n2: 5, a2: 0.08, p2: 1.7, duration: 150, delay: -110, reverse: false, opacity: 0.13, color: "var(--blue)" },
  { top: 82, height: 24, n1: 1, a1: 0.34, p1: 5.2, n2: 3, a2: 0.1, p2: 4.4, duration: 130, delay: -50, reverse: true, opacity: 0.09, color: "var(--blue2)" },
];

function pathFor(s: LineSpec): string {
  const pts: string[] = [];
  for (let i = 0; i <= STEPS * 2; i++) {
    const x = (i * TILE_W) / STEPS;
    const t = (2 * Math.PI * x) / TILE_W;
    const y = H / 2 + H * (s.a1 * Math.sin(s.n1 * t + s.p1) + s.a2 * Math.sin(s.n2 * t + s.p2));
    pts.push(`${i === 0 ? "M" : "L"}${x.toFixed(1)} ${y.toFixed(1)}`);
  }
  return pts.join("");
}

// Пока вкладка скрыта, анимацию ставим на паузу.
function useDocumentHidden(): boolean {
  const [hidden, setHidden] = useState(() => document.hidden);
  useEffect(() => {
    const onChange = () => setHidden(document.hidden);
    document.addEventListener("visibilitychange", onChange);
    return () => document.removeEventListener("visibilitychange", onChange);
  }, []);
  return hidden;
}

export function FlowBackground() {
  const hidden = useDocumentHidden();
  const paths = useMemo(() => LINES.map(pathFor), []);
  return (
    <div className={`flow-bg${hidden ? " is-paused" : ""}`} aria-hidden="true">
      {LINES.map((s, i) => (
        <svg
          key={i}
          className="flow-line"
          viewBox={`0 0 ${TILE_W * 2} ${H}`}
          preserveAspectRatio="none"
          style={{
            top: `${s.top}%`,
            height: `${s.height}vh`,
            animationDuration: `${s.duration}s`,
            animationDelay: `${s.delay}s`,
            animationDirection: s.reverse ? "reverse" : "normal",
          }}
        >
          <path
            d={paths[i]}
            fill="none"
            stroke={s.color}
            strokeOpacity={s.opacity}
            strokeWidth={1.2}
            strokeLinejoin="round"
            vectorEffect="non-scaling-stroke"
          />
        </svg>
      ))}
    </div>
  );
}
