import { useEffect, useRef, useState, useCallback } from "react"
import * as d3 from "d3"

import { useAppStore } from "../../store/useStore"

interface MemoryRiverProps {
  onSelect?: (memoryId: string) => void
  onToggleCompare?: (mode: "single" | "compare") => void
}

export function MemoryRiver({ onSelect, onToggleCompare }: MemoryRiverProps) {
  const { agent } = useAppStore()
  const { asOfMs } = useAppStore((s) => s.panel)
  const [width, setWidth] = useState(document.documentElement.clientWidth)
  const [playheadPosition, setPlayheadPosition] = useState(0)
  const [isDragging, setIsDragging] = useState(false)
  const [compareMode, setCompareMode] = useState("single")
  const [events, setEvents] = useState<any[]>([])
  const [visibleEvents, setVisibleEvents] = useState<any[]>([])
  const svgRef = useRef<any>(null)
  const [reducedMotion, setReducedMotion] = useState(false)

  // Keep width in sync with the viewport
  useEffect(() => {
    const onResize = () => setWidth(document.documentElement.clientWidth)
    window.addEventListener("resize", onResize)
    return () => window.removeEventListener("resize", onResize)
  }, [])

  // Check for reduced motion preference
  useEffect(() => {
    const mq = window.matchMedia("(prefers-reduced-motion: reduce)")
    setReducedMotion(mq.matches)
    const listener = () => setReducedMotion(mq.matches)
    mq.addEventListener("change", listener)
    return () => mq.removeEventListener("change", listener)
  }, [])

  useEffect(() => {
    async function loadTimeline() {
      if (!agent?.token) return
      try {
        const res = await fetch("/api/timeline", {
          method: "GET",
          headers: {
            "Content-Type": "application/json",
            "Authorization": `Bearer ${agent.token}`,
          },
          // asOfMs can be passed as query param or in body
        })
        if (!res.ok) throw new Error("Failed to load timeline")
        const data = await res.json()
        setEvents(data.events || [])
        updateVisibleEvents()
      } catch (err) {
        console.error("Timeline load error:", err)
      }
    }

    loadTimeline()
  }, [agent?.token, asOfMs])

  const updateVisibleEvents = () => {
    const now = asOfMs || 0
    if (compareMode === "compare") {
      // In compare mode, show events relative to both playheads
      setVisibleEvents(events)
    } else {
      // Single mode: hide events created after the playhead
      setVisibleEvents(events.filter((e: any) => e.valid_from <= now || !e.valid_from))
    }
  }

  // Playhead drag handling
  const drag = d3.drag<SVGCircleElement, any>()
    .on("start", (_e: any) => {
      setIsDragging(true)
      if (reducedMotion) return
    })
    .on("drag", (e: any) => {
      if (reducedMotion || !svgRef.current) return
      const x = d3.pointer(e)[0]
      const newPos = Math.max(0, Math.min(width - 100, x))
      setPlayheadPosition(newPos)
      // Update asOfMs proportionally (playhead drag)
    })
    .on("end", (e: any) => {
      setIsDragging(false)
      // Snap to nearest event or commit new asOfMs
      if (!reducedMotion && svgRef.current) {
        const x = d3.pointer(e)[0]
        const snapped = Math.round(x / (width - 100) * 100) / 100 * 100
        setPlayheadPosition(snapped)
      }
    })

  // Brush for zooming
  const brush = d3.brushX<SVGGElement>()
    .extent([[20, 0], [width - 20, 500]])
    .on("brush end", (e: any) => {
      // Handle brush/zoom
      const [[x1]] = e.selection || []
      setPlayheadPosition(x1 || 0)
    })

  // Render events
  const renderEvents = useCallback(() => {
    if (!svgRef.current || events.length === 0) return

    const svg = d3.select<SVGSVGElement, any>(svgRef.current)
    const height = 500
    const margin = { top: 20, right: 20, bottom: 20, left: 60 }
    const innerWidth = width - margin.left - margin.right
    const innerHeight = height - margin.top - margin.bottom

    // Scales
    const minTime = d3.min(events.map((e: any) => e.valid_from ?? 0)) || 0
    const maxTime = d3.max(events.map((e: any) => e.valid_until ?? 0)) || 100
    const timeScale = d3
      .scaleLinear()
      .domain([minTime, maxTime])
      .range([0, innerWidth])


    // Clear existing
    svg.selectAll("*").remove()

    // X-axis
    svg
      .append("g")
      .attr("transform", `translate(${margin.left}, ${margin.top})`)
      .call(d3.axisBottom(timeScale).ticks(8))
      .selectAll("text")
      .style("text-anchor", "end")
      .attr("dx", "-.8em")
      .attr("dy", ".15em")
      .attr("transform", "rotate(-45)")

    // Y-axis label
    svg
      .append("g")
      .attr("transform", `translate(${margin.left - 10}, ${innerHeight / 2 + margin.top})`)
      .attr("text-anchor", "middle")
      .style("font-size", "0.7em")
      .style("opacity", "0.6")
      .text("Concepts")

    // Playhead line
    const playheadX = (timeScale(asOfMs ?? 0) || 0) + margin.left
    svg
      .append("line")
      .attr("x1", playheadX)
      .attr("x2", playheadX)
      .attr("y1", margin.top)
      .attr("y2", innerHeight - margin.bottom)
      .attr("stroke", "#2DD4BF")
      .attr("stroke-width", 2)
      .attr("pointer-events", "all")
      .style("cursor", "ew-resize")

    // Draggable playhead
    svg
      .append("circle")
      .attr("cx", playheadX)
      .attr("cy", margin.top + 20)
      .attr("r", 6)
      .attr("fill", "#2DD4BF")
      .call(drag)

    // Session ticks (S1, S2...) - vertical markers on the time axis
    const sessionTicks = [1000000, 2000000, 3000000] // Example session boundaries
    svg
      .selectAll(".session-tick")
      .data(sessionTicks)
      .enter()
      .append("line")
      .attr("class", "session-tick")
      .attr("x1", (d: number) => timeScale(d) + margin.left)
      .attr("x2", (d: number) => timeScale(d) + margin.left)
      .attr("y1", margin.top)
      .attr("y2", innerHeight - margin.bottom)
      .attr("stroke", "#64748B")
      .attr("stroke-width", 1)
      .attr("opacity", 0.5)

    // Handoff markers (octagon icons)
    const handoffs = events.filter((e: any) => e.type === "handoff")
    svg
      .selectAll(".handoff-marker")
      .data(handoffs)
      .enter()
      .append("g")
      .attr("class", "handoff-marker")
      .attr("transform", (d: any) => `translate(${timeScale(d.valid_from ?? 0) + margin.left}, ${margin.top - 20})`)
      .on("click", (_e: any, d: any) => {
        onSelect?.(d.id)
        onToggleCompare?.("single")
      })

    // Render handoff octagon icons
    handoffs.forEach((h: any) => {
      const x = timeScale(h.valid_from ?? 0) + margin.left
      const y = margin.top - 20
      const size = 12
      svg
        .append("polygon")
        .attr("points", `
          ${x}${y + size / 2 - 4},
          ${x + size / 2 - 4}${y + size},
          ${x + size / 2 - 4}${y + size / 2 + 4},
          ${x + size / 2 + 4}${y + size},
          ${x + size / 2 + 4}${y},
          ${x + size / 2 + 4}${y - size / 2 - 4},
          ${x}${y - size / 2 - 4},
          ${x - size / 2 + 4}${y - size / 2 - 4},
          ${x - size / 2 + 4}${y},
          ${x - size / 2 + 4}${y + size / 2 + 4},
          ${x - size / 2 - 4}${y + size},
          ${x - size / 2 - 4}${y - size / 2 + 4}
        `)
        .attr("fill", "#F472B6")
        .attr("stroke", "#F472B6")
        .attr("stroke-width", 1.5)
    })

    // Decision dots on ribbons
    const decisions = events.filter((e: any) => e.type === "decision")
    svg
      .selectAll(".decision-dot")
      .data(decisions)
      .enter()
      .append("circle")
      .attr("class", "decision-dot")
      .attr("cx", (d: any) => (timeScale(d.valid_from ?? 0) || 0) + margin.left)
      .attr("cy", margin.top + 40)
      .attr("r", 4)
      .attr("fill", "#8B5CF6")
      .attr("stroke", "#E5E7EB")
      .attr("stroke-width", 1)
      .style("cursor", "pointer")
      .on("click", (_e: any, d: any) => {
        onSelect?.(d.id)
      })

    // Zoom/brush layer on top of the timeline
    svg.append("g").attr("class", "brush").call(brush)
  }, [events, visibleEvents, width, playheadPosition, compareMode, reducedMotion, brush, onSelect, onToggleCompare])

  useEffect(() => {
    renderEvents()
  }, [renderEvents])

  return (
    <div className="min-h-screen p-6 bg-bg text-text">
      <div className="mb-4 flex items-center justify-between">
        <h1 className="mb-0 text-2xl font-bold text-text">Memory River</h1>
        <button
          onClick={() => setCompareMode(compareMode === "compare" ? "single" : "compare")}
          className="rounded-md border border-border bg-surface px-3 py-1.5 text-sm text-muted hover:text-accent hover:bg-bg transition-colors"
        >
          {compareMode === "single" ? "Compare mode" : "Single mode"}
        </button>
      </div>

      <p className="mb-2 text-sm text-muted">
        {visibleEvents.length} of {events.length} events shown
        <span className="ml-3 text-[0.8em]">playhead: {playheadPosition}px</span>
        {isDragging && <span className="ml-3 text-accent">dragging…</span>}
      </p>

      <svg ref={svgRef} width={width} height={500} className="w-full" />
    </div>
  )
}
