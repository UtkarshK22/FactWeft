import { useEffect, useState } from "react"
import cytoscape from "cytoscape"
import "cytoscape-fcose"

;(globalThis as any).cytoscape = cytoscape
// fcose layout is registered by the side-effect import above

import { useAppStore } from "../../store/useStore"

interface ConstellationProps {
  onNodeSelect?: (nodeId: string, nodeData: any) => void
  onProofPath?: (path: string[]) => void
  onToggleListView?: (visible: boolean) => void
}

export function Constellation({ onNodeSelect, onProofPath, onToggleListView }: ConstellationProps) {
  const { agent } = useAppStore()
  const { selectedMemoryId, asOfMs, filters } = useAppStore((s) => s.panel)
  const [cy, setCy] = useState<any>(null)
  const [layoutPositions, setLayoutPositions] = useState<Map<string, { x: number; y: number }>>(new Map())
  const [isListView, setIsListView] = useState(false)
  const [proofPath, setProofPath] = useState<string[]>([])

  useEffect(() => {
    return () => {
      if (cy) {
        cy.destroy()
      }
    }
  }, [cy])

  useEffect(() => {
    if (!cy) return
    // Apply cached layout positions
    const nodes = cy.nodes()
    nodes.each((ele: any) => {
      const pos = layoutPositions.get(ele.id())
      if (pos) {
        ele.position({ x: pos.x, y: pos.y })
      }
    })
    cy.layout({ name: "fcose", fit: true }).stop()
  }, [cy, layoutPositions])

  useEffect(() => {
    async function loadGraph() {
      if (!agent?.token) return
      try {
        const res = await fetch("/api/graph/neighborhood", {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            "Authorization": `Bearer ${agent.token}`,
          },
          body: JSON.stringify({ asOfMs, filters }),
        })
        if (!res.ok) throw new Error("Failed to load graph")
        const data = await res.json()
        initCytoscape(data)
      } catch (err) {
        console.error("Graph load error:", err)
      }
    }
    loadGraph()
  }, [agent, asOfMs, JSON.stringify(filters)])

  const initCytoscape = (data: any) => {
    if (cy) {
      cy.destroy()
    }
    const container = document.getElementById("constellation-cy") as HTMLElement
    if (!container) return

    // Backend /api/graph/neighborhood returns { nodes, edges } (GraphNode/GraphEdge)
    const elements = [
      ...(data?.nodes ?? []).map((n: any) => ({
        data: { ...n, label: n.properties?.label ?? n.properties?.name ?? n.id },
        classes:
          (n.labels ?? [])
            .map((l: string) => String(l).toLowerCase())
            .find((l: string) => ["memory", "concept", "source", "agent", "handoff", "decision"].includes(l)) ?? "",
      })),
      ...(data?.edges ?? []).map((e: any) => {
        const type = String(e.type ?? "").toLowerCase()
        const cls = type.includes("exclud")
          ? "excludes"
          : type.includes("support")
            ? "support"
            : type.includes("supersed") || type.includes("contradict")
              ? "conflict"
              : type.includes("includ")
                ? "includes"
                : ""
        return { data: e, classes: cls }
      }),
    ]

    const cyInstance = cytoscape({
      container,
      elements,
      style: [
        // Base node style
        {
          selector: "node",
          css: {
            "content": "data(label)",
            "font-family": "Inter, system-ui, sans-serif",
            "font-size": "10px",
            "text-valign": "center",
            "text-halign": "center",
            "padding": "6px",
            "border-width": "2px",
            "opacity": 1,
          },
        },

        // Memory nodes: round-rectangle
        {
          selector: ".memory",
          css: {
            "shape": "round-rectangle",
            "width": "130px",
            "height": "50px",
            "min-width": "130px",
            "min-height": "50px",
            "background-color": "#111827",
            "color": "#E5E7EB",
          },
        },

        // Active memory: solid teal ring
        {
          selector: ".memory.active",
          css: {
            "border-color": "#2DD4BF",
            "border-style": "solid",
            "background-color": "rgba(45, 212, 191, 0.1)",
          },
        },

        // Contested memory: double amber ring + alert icon
        {
          selector: ".memory.contested",
          css: {
            "border-color": "#F59E0B",
            "border-style": "double",
            "background-color": "rgba(245, 158, 11, 0.1)",
          },
        },

        // Superseded memory: dashed slate, 55% opacity
        {
          selector: ".memory.superseded",
          css: {
            "border-color": "#6B7280",
            "border-style": "dashed",
            "opacity": 0.55,
            "background-color": "rgba(107, 114, 128, 0.1)",
          },
        },

        // Concept nodes: diamond
        {
          selector: ".concept",
          css: {
            "shape": "diamond",
            "width": "50px",
            "height": "50px",
            "min-width": "50px",
            "min-height": "50px",
            "background-color": "#1E293B",
            "color": "#E5E7EB",
          },
        },

        // Source nodes: rectangle (document look) with authority pip row
        {
          selector: ".source",
          css: {
            "shape": "rectangle",
            "width": "110px",
            "height": "38px",
            "min-width": "110px",
            "min-height": "38px",
            "background-color": "#1E293B",
            "color": "#E5E7EB",
            "padding": "4px",
            "font-size": "0.65em",
          },
        },

        // Agent nodes: hexagon in violet
        {
          selector: ".agent",
          css: {
            "shape": "hexagon",
            "width": "44px",
            "height": "44px",
            "min-width": "44px",
            "min-height": "44px",
            "background-color": "#1E293B",
            "color": "#E5E7EB",
            "border-color": "#8B5CF6",
            "border-width": "2px",
          },
        },

        // Handoff nodes: octagon
        {
          selector: ".handoff",
          css: {
            "shape": "octagon",
            "width": "44px",
            "height": "44px",
            "min-width": "44px",
            "min-height": "44px",
            "background-color": "#1E293B",
            "color": "#E5E7EB",
            "border-color": "#F472B6",
            "border-width": "2px",
          },
        },

        // Decision nodes: small circle
        {
          selector: ".decision",
          css: {
            "shape": "ellipse",
            "width": "24px",
            "height": "24px",
            "min-width": "24px",
            "min-height": "24px",
            "background-color": "#1E293B",
            "color": "#E5E7EB",
          },
        },

        // Base edge style
        {
          selector: "edge",
          css: {
            "line-color": "#64748B",
            "target-arrow-shape": "triangle",
            "width": 1.5,
          },
        },

        // Support/about edges: solid
        {
          selector: ".support",
          css: {
            "line-color": "#2DD4BF",
            "line-style": "solid",
            "target-arrow-shape": "triangle",
          },
        },

        // SUPERSEDES/CONTRADICTS: dashed with labels on hover
        {
          selector: ".conflict",
          css: {
            "line-color": "#F59E0B",
            "line-style": "dashed",
            "target-arrow-shape": "triangle",
            "width": 1.5,
          },
        },

        // INCLUDES edges: teal
        {
          selector: ".includes",
          css: {
            "line-color": "#2DD4BF",
            "line-style": "solid",
            "width": 1.5,
          },
        },

        // EXCLUDES edges: rose with reason code label
        {
          selector: ".excludes",
          css: {
            "line-color": "#F43F5E",
            "line-style": "dashed",
            "width": 1.5,
          },
        },

        // Hover highlight: dim rest, highlight neighbors
        {
          selector: ".highlighted",
          css: {
            "opacity": 0.3,
          },
        },

        // Selected node
        {
          selector: ".selected",
          css: {
            "background-color": "#3B82F6",
            "color": "white",
            "border-color": "#3B82F6",
          },
        },

        // Proof path node
        {
          selector: ".proof-step",
          css: {
            "background-color": "#F97316",
            "color": "white",
            "border-color": "#F97316",
            "border-width": "3px",
          },
        },
      ],
    })

    // Interaction: select memory node on tap
    cyInstance.nodes().on("tap", (evt: any) => {
      const node = evt.target
      onNodeSelect?.(node.id(), node.data())
    })

    // Interaction: show proof path between two nodes on edge tap
    cyInstance.edges().on("tap", (evt: any) => {
      const edge = evt.target
      const path = [edge.source().id(), edge.target().id()]
      setProofPath(path)
      onProofPath?.(path)
    })

    // Persist positions when the user drags a node
    cyInstance.nodes().on("dragstop", (evt: any) => {
      const node = evt.target
      setLayoutPositions(new Map(layoutPositions).set(node.id(), node.position()))
    })

    // Highlight the selected memory node
    if (selectedMemoryId) {
      cyInstance.nodes().removeClass("active")
      cyInstance.getElementById(selectedMemoryId).addClass("active")
    }

    cyInstance.layout({ name: "fcose" }).run()
    setCy(cyInstance)
  }

  return (
    <div className="relative h-full w-full">
      <div id="constellation-cy" className="h-full w-full min-h-[480px]" />

      {/* View toggle */}
      <button
        onClick={() => {
          setIsListView(!isListView)
          onToggleListView?.(!isListView)
        }}
        className="absolute top-2 right-2 rounded-md border border-border bg-surface px-3 py-1.5 text-sm text-muted hover:text-accent hover:bg-bg transition-colors"
      >
        {isListView ? "Graph view" : "List view"}
      </button>

      {/* List view fallback */}
      {isListView && (
        <div className="absolute inset-0 overflow-y-auto bg-bg/95 p-4 text-sm text-muted">
          <p>Select a node in the graph view to inspect it.</p>
        </div>
      )}

      {/* Proof path indicator */}
      {proofPath.length > 0 && (
        <div className="absolute bottom-4 left-1/2 -translate-x-1/2 rounded-md border border-border bg-surface px-4 py-2 text-sm text-text">
          Proof path: {proofPath.join(" → ")}
        </div>
      )}
    </div>
  )
}
