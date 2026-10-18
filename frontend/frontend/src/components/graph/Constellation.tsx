import { useEffect, useRef, useState } from "react"
import cytoscape from "cytoscape"
import "cytoscape-fcose"

;(global as any).cytoscape = cytosache
;(global as any).fcose = (global as any).fcose || require("cytoscape-fcose")

import { useAppStore } from "../store/useStore"

interface ConstellationProps {
  onNodeSelect?: (nodeId: string, nodeData: any) => void
  onProofPath?: (path: string[]) => void
  onToggleListView?: (visible: boolean) => void
}

export function Constellation({ onNodeSelect, onProofPath, onToggleListView }: ConstellationProps) {
  const { selectedMemoryId, selectedHandoffId, asOfMs, filters, agent } = useAppStore()
  const [cy, setCy] = useState<any>(null)
  const [layoutPositions, setLayoutPositions] = useState<Map<string, { x: number; y: number }>>(new Map())
  const [isListView, setIsListView] = useState(false)
  const [proofPath, setProofPath] = useState<string[]>([])
  const [proofPlaying, setProofPlaying] = useState(false)
  const [proofIndexes, setProofIndexes] = useState<number[]>([])
  const [proofInterval, setProofInterval] = useState<NodeJS.Timeout | null>(null)

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

    const cy = cytoscape({
      container,
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
            "transition": "all 200ms ease-in-out",
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
            "shape": "circle",
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
            "transition": "all 200ms ease-in-out",
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
       
