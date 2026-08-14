"use client";

import { useEffect, useRef } from "react";

type Spark = {
  x: number;
  y: number;
  vx: number;
  vy: number;
  life: number;
  maxLife: number;
  size: number;
};

function createSpark(width: number, height: number): Spark {
  const maxLife = 60 + Math.random() * 80;
  return {
    x: width * (0.3 + Math.random() * 0.4),
    y: height * (0.55 + Math.random() * 0.25),
    vx: (Math.random() - 0.5) * 0.6,
    vy: -0.4 - Math.random() * 0.8,
    life: maxLife,
    maxLife,
    size: 1 + Math.random() * 2,
  };
}

export function ForgeBackground() {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const prefersReducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    let animationId = 0;
    let sparks: Spark[] = [];
    let width = 0;
    let height = 0;

    const resize = () => {
      const dpr = Math.min(window.devicePixelRatio || 1, 2);
      width = canvas.offsetWidth;
      height = canvas.offsetHeight;
      canvas.width = width * dpr;
      canvas.height = height * dpr;
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    };

    const drawStatic = () => {
      ctx.clearRect(0, 0, width, height);

      const gradient = ctx.createRadialGradient(
        width * 0.5,
        height * 0.65,
        0,
        width * 0.5,
        height * 0.65,
        width * 0.45,
      );
      gradient.addColorStop(0, "rgba(232, 93, 4, 0.12)");
      gradient.addColorStop(0.5, "rgba(193, 68, 14, 0.05)");
      gradient.addColorStop(1, "rgba(12, 14, 18, 0)");
      ctx.fillStyle = gradient;
      ctx.fillRect(0, 0, width, height);

      for (let i = 0; i < 24; i++) {
        const x = width * (0.25 + Math.random() * 0.5);
        const y = height * (0.5 + Math.random() * 0.35);
        const alpha = 0.15 + Math.random() * 0.25;
        ctx.beginPath();
        ctx.arc(x, y, 1 + Math.random(), 0, Math.PI * 2);
        ctx.fillStyle = `rgba(255, 179, 71, ${alpha})`;
        ctx.fill();
      }
    };

    const drawFrame = () => {
      ctx.clearRect(0, 0, width, height);

      const gradient = ctx.createRadialGradient(
        width * 0.5,
        height * 0.7,
        0,
        width * 0.5,
        height * 0.7,
        width * 0.5,
      );
      gradient.addColorStop(0, "rgba(232, 93, 4, 0.18)");
      gradient.addColorStop(0.4, "rgba(193, 68, 14, 0.06)");
      gradient.addColorStop(1, "rgba(12, 14, 18, 0)");
      ctx.fillStyle = gradient;
      ctx.fillRect(0, 0, width, height);

      if (sparks.length < 40 && Math.random() < 0.35) {
        sparks.push(createSpark(width, height));
      }

      sparks = sparks.filter((spark) => {
        spark.x += spark.vx;
        spark.y += spark.vy;
        spark.vy -= 0.008;
        spark.life -= 1;

        const opacity = spark.life / spark.maxLife;
        if (opacity <= 0) return false;

        ctx.beginPath();
        ctx.arc(spark.x, spark.y, spark.size * opacity, 0, Math.PI * 2);
        ctx.fillStyle = `rgba(255, 179, 71, ${opacity * 0.9})`;
        ctx.fill();

        if (spark.size > 1.2) {
          ctx.beginPath();
          ctx.moveTo(spark.x, spark.y);
          ctx.lineTo(spark.x - spark.vx * 3, spark.y - spark.vy * 3);
          ctx.strokeStyle = `rgba(232, 93, 4, ${opacity * 0.4})`;
          ctx.lineWidth = 0.5;
          ctx.stroke();
        }

        return true;
      });

      animationId = requestAnimationFrame(drawFrame);
    };

    resize();
    if (prefersReducedMotion) {
      drawStatic();
    } else {
      drawFrame();
    }

    window.addEventListener("resize", resize);

    const motionQuery = window.matchMedia("(prefers-reduced-motion: reduce)");
    const onMotionChange = (event: MediaQueryListEvent) => {
      cancelAnimationFrame(animationId);
      sparks = [];
      if (event.matches) {
        drawStatic();
      } else {
        drawFrame();
      }
    };
    motionQuery.addEventListener("change", onMotionChange);

    return () => {
      cancelAnimationFrame(animationId);
      window.removeEventListener("resize", resize);
      motionQuery.removeEventListener("change", onMotionChange);
    };
  }, []);

  return (
    <canvas
      ref={canvasRef}
      className="pointer-events-none absolute inset-0 h-full w-full"
      aria-hidden="true"
    />
  );
}
