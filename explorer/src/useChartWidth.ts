import {useEffect, useState} from 'react';

/** Keep SVG coordinates in CSS pixels so taller charts retain readable labels. */
export function useChartWidth() {
  const [node, ref] = useState<SVGSVGElement | null>(null);
  const [width, setWidth] = useState(600);
  useEffect(() => {
    if (!node) return;
    const observer = new ResizeObserver(([entry]) => setWidth(Math.max(240, entry.contentRect.width)));
    observer.observe(node);
    return () => observer.disconnect();
  }, [node]);
  return {ref, width};
}
