'use client';

import { useEffect, useRef, useState, useCallback } from 'react';
import {
  forceSimulation,
  forceLink,
  forceManyBody,
  forceCenter,
  forceCollide,
  type SimulationNodeDatum,
  type SimulationLinkDatum,
} from 'd3-force';
import type { PersonConnectionsResponse, PersonConnection } from '@/lib/api';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------
interface GraphNode extends SimulationNodeDatum {
  id: string;
  name: string;
  shortBio: string | null;
  imageUrl: string | null;
  trustScore: number;
  aliases: string[];
  isCenter: boolean;
}

interface GraphLink extends SimulationLinkDatum<GraphNode> {
  relationship: string;
  direction: string;
}

interface HoveredNode {
  node: GraphNode;
  screenX: number;
  screenY: number;
}

interface Props {
  data: PersonConnectionsResponse;
  onPersonClick?: (personId: string) => void;
}

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------
const NODE_RADIUS = 28;
const CENTER_RADIUS = 36;
const ARROW_SIZE = 8;
const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

const REL_COLORS: Record<string, string> = {
  KNOWS: '#3b82f6',
  FRIEND: '#22c55e',
  FAMILY: '#a855f7',
  COLLEAGUE: '#f59e0b',
  WORKS_WITH: '#f59e0b',
  MANAGES: '#ef4444',
  REPORTS_TO: '#ef4444',
  MENTOR: '#06b6d4',
  PARTNER: '#ec4899',
  NEIGHBOR: '#84cc16',
  CLASSMATE: '#8b5cf6',
};

function getRelColor(rel: string): string {
  return REL_COLORS[rel] || '#6b7280';
}

function getTrustColor(score: number): string {
  if (score >= 0.7) return '#22c55e';
  if (score >= 0.4) return '#f59e0b';
  return '#ef4444';
}

/** Cached theme colors — updated once per theme change, not every frame. */
interface ThemeColors {
  background: string;
  surface: string;
  foreground: string;
  border: string;
  accent: string;
  muted: string;
}

function readThemeColors(el: HTMLElement): ThemeColors {
  const s = getComputedStyle(el);
  return {
    background: s.getPropertyValue('--background').trim() || '#ffffff',
    surface: s.getPropertyValue('--surface').trim() || '#ffffff',
    foreground: s.getPropertyValue('--foreground').trim() || '#171717',
    border: s.getPropertyValue('--border').trim() || '#e5e7eb',
    accent: s.getPropertyValue('--accent').trim() || '#3b82f6',
    muted: s.getPropertyValue('--muted').trim() || '#6b7280',
  };
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------
export default function ConnectionsGraph({ data, onPersonClick }: Props) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const nodesRef = useRef<GraphNode[]>([]);
  const linksRef = useRef<GraphLink[]>([]);
  const imagesRef = useRef<Map<string, HTMLImageElement>>(new Map());
  const simRef = useRef<ReturnType<typeof forceSimulation<GraphNode>> | null>(null);
  const rafRef = useRef<number>(0);
  const themeRef = useRef<ThemeColors>({
    background: '#ffffff', surface: '#ffffff', foreground: '#171717',
    border: '#e5e7eb', accent: '#3b82f6', muted: '#6b7280',
  });

  // Interaction state
  const [hoveredNode, setHoveredNode] = useState<HoveredNode | null>(null);
  const hoveredIdRef = useRef<string | null>(null);
  const [draggedNode, setDraggedNode] = useState<GraphNode | null>(null);
  const transformRef = useRef({ x: 0, y: 0, scale: 1 });
  const isPanningRef = useRef(false);
  const lastMouseRef = useRef({ x: 0, y: 0 });
  const dragDistRef = useRef(0);

  // Build adjacency set for highlight dimming
  const adjacencyRef = useRef<Map<string, Set<string>>>(new Map());

  // Build graph data from API response
  useEffect(() => {
    if (!data.person) return;

    const centerNode: GraphNode = {
      id: data.person.id,
      name: data.person.name,
      shortBio: data.person.short_bio,
      imageUrl: data.person.face_image_url,
      trustScore: data.person.trust_score,
      aliases: data.person.aliases || [],
      isCenter: true,
      x: 0,
      y: 0,
    };

    const nodeMap = new Map<string, GraphNode>();
    nodeMap.set(centerNode.id, centerNode);

    const links: GraphLink[] = [];
    const adj = new Map<string, Set<string>>();

    data.connections.forEach((conn: PersonConnection) => {
      const pid = conn.person.id;
      if (!nodeMap.has(pid)) {
        nodeMap.set(pid, {
          id: pid,
          name: conn.person.name,
          shortBio: conn.person.short_bio,
          imageUrl: conn.person.face_image_url,
          trustScore: conn.person.trust_score,
          aliases: conn.person.aliases || [],
          isCenter: false,
        });
      }
      links.push({
        source: centerNode.id,
        target: pid,
        relationship: conn.relationship,
        direction: conn.direction,
      });

      // Build adjacency
      if (!adj.has(centerNode.id)) adj.set(centerNode.id, new Set());
      if (!adj.has(pid)) adj.set(pid, new Set());
      adj.get(centerNode.id)!.add(pid);
      adj.get(pid)!.add(centerNode.id);
    });

    const nodes = Array.from(nodeMap.values());
    nodesRef.current = nodes;
    linksRef.current = links;
    adjacencyRef.current = adj;

    // Preload images
    nodes.forEach((node) => {
      if (node.imageUrl) {
        const img = new Image();
        img.crossOrigin = 'anonymous';
        img.src = node.imageUrl.startsWith('http') ? node.imageUrl : `${API_BASE}${node.imageUrl}`;
        img.onload = () => {
          imagesRef.current.set(node.id, img);
        };
      }
    });

    // Setup simulation
    const linkDistance = Math.max(160, 120 + nodes.length * 4);

    const sim = forceSimulation<GraphNode>(nodes)
      .force(
        'link',
        forceLink<GraphNode, GraphLink>(links)
          .id((d) => d.id)
          .distance(linkDistance)
      )
      .force('charge', forceManyBody().strength(-400))
      .force('center', forceCenter(0, 0))
      .force('collide', forceCollide(NODE_RADIUS + 12))
      .alphaDecay(0.02);

    simRef.current = sim;

    return () => {
      sim.stop();
    };
  }, [data]);

  // Cache theme colors & watch for changes
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    themeRef.current = readThemeColors(canvas);

    const observer = new MutationObserver(() => {
      themeRef.current = readThemeColors(canvas);
    });
    observer.observe(document.documentElement, { attributes: true, attributeFilter: ['data-theme'] });
    return () => observer.disconnect();
  }, []);

  // Coordinate transforms
  const screenToWorld = useCallback((sx: number, sy: number) => {
    const t = transformRef.current;
    const canvas = canvasRef.current;
    if (!canvas) return { x: 0, y: 0 };
    return {
      x: (sx - canvas.width / 2 - t.x) / t.scale,
      y: (sy - canvas.height / 2 - t.y) / t.scale,
    };
  }, []);

  const worldToScreen = useCallback((wx: number, wy: number) => {
    const t = transformRef.current;
    const canvas = canvasRef.current;
    if (!canvas) return { x: 0, y: 0 };
    return {
      x: wx * t.scale + canvas.width / 2 + t.x,
      y: wy * t.scale + canvas.height / 2 + t.y,
    };
  }, []);

  // Find node at position
  const nodeAtPos = useCallback((sx: number, sy: number): GraphNode | null => {
    const world = screenToWorld(sx, sy);
    for (let i = nodesRef.current.length - 1; i >= 0; i--) {
      const n = nodesRef.current[i];
      const r = n.isCenter ? CENTER_RADIUS : NODE_RADIUS;
      const dx = (n.x || 0) - world.x;
      const dy = (n.y || 0) - world.y;
      if (dx * dx + dy * dy < r * r) return n;
    }
    return null;
  }, [screenToWorld]);

  // Render loop
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    function draw() {
      if (!ctx || !canvas) return;
      const w = canvas.width;
      const h = canvas.height;
      const t = transformRef.current;
      const theme = themeRef.current;
      const hovId = hoveredIdRef.current;
      const adjSet = hovId ? adjacencyRef.current.get(hovId) : null;

      ctx.clearRect(0, 0, w, h);
      ctx.save();
      ctx.translate(w / 2 + t.x, h / 2 + t.y);
      ctx.scale(t.scale, t.scale);

      // Draw links
      linksRef.current.forEach((link) => {
        const source = link.source as GraphNode;
        const target = link.target as GraphNode;
        if (source.x == null || target.x == null) return;

        const color = getRelColor(link.relationship);

        // Dim if hovering a node and this edge is not connected to it
        const isDimmed = hovId !== null &&
          (source.id !== hovId && target.id !== hovId);

        ctx.globalAlpha = isDimmed ? 0.12 : 0.6;

        // Line
        ctx.beginPath();
        ctx.moveTo(source.x, source.y!);
        ctx.lineTo(target.x, target.y!);
        ctx.strokeStyle = color;
        ctx.lineWidth = isDimmed ? 1 : 2;
        ctx.stroke();

        // Arrow at midpoint showing direction
        if (!isDimmed) {
          const mx = (source.x + target.x) / 2;
          const my = (source.y! + target.y!) / 2;
          const angle = Math.atan2(target.y! - source.y!, target.x - source.x);

          ctx.globalAlpha = 0.7;
          ctx.save();
          ctx.translate(mx, my);
          ctx.rotate(angle);
          ctx.beginPath();
          ctx.moveTo(ARROW_SIZE, 0);
          ctx.lineTo(-ARROW_SIZE * 0.6, -ARROW_SIZE * 0.5);
          ctx.lineTo(-ARROW_SIZE * 0.6, ARROW_SIZE * 0.5);
          ctx.closePath();
          ctx.fillStyle = color;
          ctx.fill();
          ctx.restore();
        }

        ctx.globalAlpha = 1;

        // Relationship label at midpoint (only if not dimmed)
        if (!isDimmed) {
          const mx = (source.x + target.x) / 2;
          const my = (source.y! + target.y!) / 2;
          const fontSize = 10;
          ctx.font = `500 ${fontSize}px Arial`;
          ctx.textAlign = 'center';
          ctx.textBaseline = 'middle';

          const label = link.relationship.replace(/_/g, ' ');
          const metrics = ctx.measureText(label);
          const pad = 4;

          // Label background
          ctx.fillStyle = theme.background;
          ctx.fillRect(
            mx - metrics.width / 2 - pad,
            my - fontSize / 2 - pad + 12,
            metrics.width + pad * 2,
            fontSize + pad * 2
          );

          // Label text
          ctx.fillStyle = color;
          ctx.fillText(label, mx, my + 12);
        }
      });

      // Draw nodes
      nodesRef.current.forEach((node) => {
        if (node.x == null || node.y == null) return;
        const r = node.isCenter ? CENTER_RADIUS : NODE_RADIUS;
        const img = imagesRef.current.get(node.id);

        // Dim if hovering another node and this one isn't connected
        const isDimmed = hovId !== null && node.id !== hovId &&
          !(adjSet && adjSet.has(node.id));

        if (isDimmed) {
          ctx.globalAlpha = 0.2;
        }

        // Hover glow ring
        const isHovered = hovId === node.id;
        if (isHovered) {
          ctx.shadowColor = theme.accent;
          ctx.shadowBlur = 16;
        } else {
          ctx.shadowColor = 'rgba(0,0,0,0.12)';
          ctx.shadowBlur = 6;
        }
        ctx.shadowOffsetY = isHovered ? 0 : 2;

        // Circle background
        ctx.beginPath();
        ctx.arc(node.x, node.y, r, 0, Math.PI * 2);
        ctx.fillStyle = theme.surface;
        ctx.fill();

        // Border
        ctx.shadowColor = 'transparent';
        ctx.shadowBlur = 0;
        ctx.shadowOffsetY = 0;

        if (isHovered) {
          ctx.strokeStyle = theme.accent;
          ctx.lineWidth = 3;
        } else if (node.isCenter) {
          ctx.strokeStyle = theme.accent;
          ctx.lineWidth = 3;
        } else {
          ctx.strokeStyle = theme.border;
          ctx.lineWidth = 1.5;
        }
        ctx.stroke();

        // Image or initials
        if (img && img.complete && img.naturalWidth > 0) {
          ctx.save();
          ctx.beginPath();
          ctx.arc(node.x, node.y, r - 2, 0, Math.PI * 2);
          ctx.clip();
          ctx.drawImage(img, node.x - r + 2, node.y - r + 2, (r - 2) * 2, (r - 2) * 2);
          ctx.restore();
        } else {
          const initials = node.name
            .split(' ')
            .map((w) => w[0])
            .join('')
            .toUpperCase()
            .slice(0, 2);
          const fontSize = r * 0.7;
          ctx.font = `600 ${fontSize}px Arial`;
          ctx.fillStyle = theme.muted;
          ctx.textAlign = 'center';
          ctx.textBaseline = 'middle';
          ctx.fillText(initials, node.x, node.y);
        }

        // Name label below node
        ctx.font = `${node.isCenter ? '600' : '400'} 12px Arial`;
        ctx.fillStyle = theme.foreground;
        ctx.textAlign = 'center';
        ctx.textBaseline = 'top';
        ctx.fillText(node.name, node.x, node.y + r + 6);

        ctx.globalAlpha = 1;
      });

      ctx.restore();
      rafRef.current = requestAnimationFrame(draw);
    }

    rafRef.current = requestAnimationFrame(draw);
    return () => cancelAnimationFrame(rafRef.current);
  }, [data]);

  // Resize handler
  useEffect(() => {
    const container = containerRef.current;
    const canvas = canvasRef.current;
    if (!container || !canvas) return;

    const resize = () => {
      const rect = container.getBoundingClientRect();
      canvas.width = rect.width;
      canvas.height = rect.height;
      canvas.style.width = `${rect.width}px`;
      canvas.style.height = `${rect.height}px`;
    };

    resize();
    const observer = new ResizeObserver(resize);
    observer.observe(container);
    return () => observer.disconnect();
  }, []);

  // Mouse/touch interactions
  const handlePointerDown = useCallback(
    (e: React.PointerEvent) => {
      const canvas = canvasRef.current;
      if (!canvas) return;
      const rect = canvas.getBoundingClientRect();
      const sx = e.clientX - rect.left;
      const sy = e.clientY - rect.top;

      dragDistRef.current = 0;

      const node = nodeAtPos(sx, sy);
      if (node) {
        setDraggedNode(node);
        node.fx = node.x;
        node.fy = node.y;
        simRef.current?.alphaTarget(0.3).restart();
        canvas.style.cursor = 'grabbing';
      } else {
        isPanningRef.current = true;
        canvas.style.cursor = 'grabbing';
      }
      lastMouseRef.current = { x: e.clientX, y: e.clientY };
      canvas.setPointerCapture(e.pointerId);
    },
    [nodeAtPos]
  );

  const handlePointerMove = useCallback(
    (e: React.PointerEvent) => {
      const canvas = canvasRef.current;
      if (!canvas) return;
      const rect = canvas.getBoundingClientRect();
      const sx = e.clientX - rect.left;
      const sy = e.clientY - rect.top;
      const dx = e.clientX - lastMouseRef.current.x;
      const dy = e.clientY - lastMouseRef.current.y;
      lastMouseRef.current = { x: e.clientX, y: e.clientY };

      dragDistRef.current += Math.abs(dx) + Math.abs(dy);

      if (draggedNode) {
        const world = screenToWorld(sx, sy);
        draggedNode.fx = world.x;
        draggedNode.fy = world.y;
        setHoveredNode(null);
        hoveredIdRef.current = null;
      } else if (isPanningRef.current) {
        transformRef.current.x += dx;
        transformRef.current.y += dy;
        setHoveredNode(null);
        hoveredIdRef.current = null;
      } else {
        // Hover detection
        const node = nodeAtPos(sx, sy);
        if (node) {
          const screen = worldToScreen(node.x || 0, node.y || 0);
          setHoveredNode({ node, screenX: screen.x, screenY: screen.y });
          hoveredIdRef.current = node.id;
          canvas.style.cursor = 'pointer';
        } else {
          setHoveredNode(null);
          hoveredIdRef.current = null;
          canvas.style.cursor = 'grab';
        }
      }
    },
    [draggedNode, nodeAtPos, screenToWorld, worldToScreen]
  );

  const handlePointerUp = useCallback(() => {
    const canvas = canvasRef.current;
    if (draggedNode) {
      draggedNode.fx = null;
      draggedNode.fy = null;
      simRef.current?.alphaTarget(0);
      setDraggedNode(null);
    }
    isPanningRef.current = false;
    if (canvas) canvas.style.cursor = 'grab';
  }, [draggedNode]);

  const handleClick = useCallback(
    (e: React.MouseEvent) => {
      // Ignore clicks that were actually drags
      if (dragDistRef.current > 5) return;

      const canvas = canvasRef.current;
      if (!canvas || !onPersonClick) return;
      const rect = canvas.getBoundingClientRect();
      const sx = e.clientX - rect.left;
      const sy = e.clientY - rect.top;
      const node = nodeAtPos(sx, sy);
      if (node) {
        onPersonClick(node.id);
      }
    },
    [nodeAtPos, onPersonClick]
  );

  const handleWheel = useCallback((e: React.WheelEvent) => {
    e.preventDefault();
    const factor = e.deltaY > 0 ? 0.9 : 1.1;
    const t = transformRef.current;
    const newScale = Math.max(0.2, Math.min(3, t.scale * factor));

    // Zoom toward cursor
    const canvas = canvasRef.current;
    if (canvas) {
      const rect = canvas.getBoundingClientRect();
      const cx = e.clientX - rect.left - canvas.width / 2;
      const cy = e.clientY - rect.top - canvas.height / 2;
      t.x = cx - (cx - t.x) * (newScale / t.scale);
      t.y = cy - (cy - t.y) * (newScale / t.scale);
    }
    t.scale = newScale;
  }, []);

  // Find the relationship label for hovered node
  const hoveredRelationship = hoveredNode
    ? linksRef.current.find(
        (l) =>
          ((l.source as GraphNode).id === hoveredNode.node.id ||
           (l.target as GraphNode).id === hoveredNode.node.id) &&
          !hoveredNode.node.isCenter
      )?.relationship || null
    : null;

  // Clamp tooltip position within viewport
  const tooltipStyle = hoveredNode && !draggedNode
    ? (() => {
        const container = containerRef.current;
        if (!container) return { left: 0, top: 0 };
        const rect = container.getBoundingClientRect();
        const tooltipW = 260;
        const tooltipH = 120;
        let left = hoveredNode.screenX + 20;
        let top = hoveredNode.screenY - 20;

        // Clamp right
        if (left + tooltipW > rect.width) left = hoveredNode.screenX - tooltipW - 10;
        // Clamp bottom
        if (top + tooltipH > rect.height) top = rect.height - tooltipH - 8;
        // Clamp top
        if (top < 8) top = 8;
        // Clamp left
        if (left < 8) left = 8;

        return { left, top };
      })()
    : null;

  // Empty state
  if (!data.person) {
    return (
      <div className="flex items-center justify-center h-full" style={{ color: 'var(--muted)' }}>
        Person not found.
      </div>
    );
  }

  if (data.connections.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center h-full gap-3" style={{ color: 'var(--muted)' }}>
        <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
          <circle cx="12" cy="12" r="3" />
          <path d="M12 1v4M12 19v4M4.22 4.22l2.83 2.83M16.95 16.95l2.83 2.83M1 12h4M19 12h4M4.22 19.78l2.83-2.83M16.95 7.05l2.83-2.83" />
        </svg>
        <p className="text-sm font-medium">No connections found</p>
        <p className="text-xs" style={{ color: 'var(--muted-foreground)' }}>
          This person has no relationships in the graph yet.
        </p>
      </div>
    );
  }

  return (
    <div ref={containerRef} className="relative w-full h-full" style={{ minHeight: 400 }}>
      <canvas
        ref={canvasRef}
        onPointerDown={handlePointerDown}
        onPointerMove={handlePointerMove}
        onPointerUp={handlePointerUp}
        onClick={handleClick}
        onWheel={handleWheel}
        style={{ cursor: 'grab', touchAction: 'none' }}
        className="w-full h-full"
      />

      {/* Legend */}
      <div
        className="absolute bottom-3 left-3 rounded-lg px-3 py-2 text-xs flex flex-wrap gap-x-4 gap-y-1"
        style={{
          background: 'var(--surface)',
          border: '1px solid var(--border)',
          boxShadow: 'var(--shadow-sm)',
          color: 'var(--foreground)',
        }}
      >
        {[...new Set(data.connections.map((c) => c.relationship))].map((rel) => (
          <span key={rel} className="flex items-center gap-1.5">
            <span
              className="inline-block w-3 h-0.5 rounded"
              style={{ background: getRelColor(rel) }}
            />
            {rel.replace(/_/g, ' ')}
          </span>
        ))}
      </div>

      {/* Hover tooltip with photo + trust bar */}
      {hoveredNode && !draggedNode && tooltipStyle && (
        <div
          className="absolute pointer-events-none rounded-xl p-3 z-10 animate-fadeIn"
          style={{
            left: tooltipStyle.left,
            top: tooltipStyle.top,
            background: 'var(--surface)',
            border: '1px solid var(--border)',
            boxShadow: 'var(--shadow-lg)',
            maxWidth: 260,
          }}
        >
          <div className="flex items-start gap-3">
            {/* Photo thumbnail */}
            {hoveredNode.node.imageUrl ? (
              <img
                src={hoveredNode.node.imageUrl.startsWith('http')
                  ? hoveredNode.node.imageUrl
                  : `${API_BASE}${hoveredNode.node.imageUrl}`}
                alt=""
                className="w-10 h-10 rounded-full object-cover shrink-0"
              />
            ) : (
              <div
                className="w-10 h-10 rounded-full flex items-center justify-center text-sm font-semibold shrink-0"
                style={{ background: 'var(--accent-light)', color: 'var(--accent)' }}
              >
                {hoveredNode.node.name.charAt(0).toUpperCase()}
              </div>
            )}

            <div className="min-w-0 flex-1">
              <p className="font-semibold text-sm truncate" style={{ color: 'var(--foreground)' }}>
                {hoveredNode.node.name}
              </p>
              {hoveredNode.node.aliases.length > 0 && (
                <p className="text-[11px] truncate" style={{ color: 'var(--muted-foreground)' }}>
                  aka {hoveredNode.node.aliases.join(', ')}
                </p>
              )}
            </div>
          </div>

          {hoveredNode.node.shortBio && (
            <p
              className="text-xs mt-2 line-clamp-2 leading-relaxed"
              style={{ color: 'var(--muted)' }}
            >
              {hoveredNode.node.shortBio}
            </p>
          )}

          {/* Trust score bar */}
          <div className="flex items-center gap-2 mt-2">
            <span className="text-[10px]" style={{ color: 'var(--muted-foreground)' }}>Trust</span>
            <div
              className="flex-1 h-1.5 rounded-full overflow-hidden"
              style={{ background: 'var(--border)' }}
            >
              <div
                className="h-full rounded-full"
                style={{
                  width: `${(hoveredNode.node.trustScore * 100).toFixed(0)}%`,
                  background: getTrustColor(hoveredNode.node.trustScore),
                }}
              />
            </div>
            <span
              className="text-[10px] font-medium"
              style={{ color: getTrustColor(hoveredNode.node.trustScore) }}
            >
              {(hoveredNode.node.trustScore * 100).toFixed(0)}%
            </span>
          </div>

          {/* Relationship badge for non-center nodes */}
          {hoveredRelationship && (
            <div className="mt-2 flex items-center gap-1.5">
              <span
                className="inline-block w-2 h-2 rounded-full"
                style={{ background: getRelColor(hoveredRelationship) }}
              />
              <span className="text-[11px] font-medium" style={{ color: getRelColor(hoveredRelationship) }}>
                {hoveredRelationship.replace(/_/g, ' ')}
              </span>
            </div>
          )}

          <p className="text-[10px] mt-2" style={{ color: 'var(--accent)' }}>
            Click to view profile
          </p>
        </div>
      )}

      {/* Zoom controls */}
      <div
        className="absolute top-3 right-3 flex flex-col rounded-lg overflow-hidden"
        style={{
          border: '1px solid var(--border)',
          boxShadow: 'var(--shadow-sm)',
        }}
      >
        <button
          onClick={() => {
            transformRef.current.scale = Math.min(3, transformRef.current.scale * 1.2);
          }}
          className="px-2.5 py-1.5 text-sm font-medium hover:opacity-80 transition-opacity"
          style={{ background: 'var(--surface)', color: 'var(--foreground)' }}
          title="Zoom in"
        >
          +
        </button>
        <div style={{ height: 1, background: 'var(--border)' }} />
        <button
          onClick={() => {
            transformRef.current.scale = Math.max(0.2, transformRef.current.scale / 1.2);
          }}
          className="px-2.5 py-1.5 text-sm font-medium hover:opacity-80 transition-opacity"
          style={{ background: 'var(--surface)', color: 'var(--foreground)' }}
          title="Zoom out"
        >
          -
        </button>
        <div style={{ height: 1, background: 'var(--border)' }} />
        <button
          onClick={() => {
            transformRef.current = { x: 0, y: 0, scale: 1 };
          }}
          className="px-2.5 py-1.5 text-xs font-medium hover:opacity-80 transition-opacity"
          style={{ background: 'var(--surface)', color: 'var(--muted)' }}
          title="Reset view"
        >
          Fit
        </button>
      </div>
    </div>
  );
}
