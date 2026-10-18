import { ReactNode, useState, useEffect } from "react"

interface SkeletonLoaderProps {
  size?: "small" | "medium" | "large"
  className?: string
}

export function SkeletonLoader({ size = "medium", className }: SkeletonLoaderProps) {
  const sizeClasses = {
    small: "h-4 w-full rounded-md mb-1",
    medium: "h-6 w-full rounded-md mb-2",
    large: "h-8 w-full rounded-md mb-3 max-w-2xl",
  }

  return (
    <div className={`
      animate-shimmer rounded-md bg-surface/50 ${sizeClasses[size]}
      ${className || ""}
    `}></div>
  )
}

// Array of skeletons for listing views
export function SkeletonListItem() {
  return (
    <div className="flex items-start gap-3 rounded-md bg-surface p-3 border border-border mb-2">
      <div className="h-5 w-2/4 rounded-b md:rounded-none md:mb-0 md:mr-3 animate-shimmer" />
      <div className="flex-1">
        <div className="h-2 w-2/3 rounded-b mb-1 animate-shimmer" />
        <div className="h-2 w-1/2 rounded-b animate-shimmer" />
      </div>
    </div>
  )
}
