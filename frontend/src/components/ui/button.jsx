import * as React from "react"
import { Slot } from "@radix-ui/react-slot"
import { cva } from "class-variance-authority";

import { cn } from "@/lib/utils"

const buttonVariants = cva(
  "inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-sm text-sm font-medium uppercase tracking-wider cyber-chamfer-sm transition-all duration-150 focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring disabled:pointer-events-none disabled:opacity-40 disabled:saturate-50 active:scale-[0.97] [&_svg]:pointer-events-none [&_svg]:size-4 [&_svg]:shrink-0",
  {
    variants: {
      variant: {
        default:
          "bg-[hsl(var(--primary))] text-[hsl(var(--primary-foreground))] font-semibold hover:brightness-110 hover:shadow-[0_0_14px_rgba(0,255,245,0.45)]",
        destructive:
          "border border-[hsl(var(--neon-magenta))]/60 bg-[hsl(var(--neon-magenta))]/10 text-[hsl(var(--neon-magenta))] hover:bg-[hsl(var(--neon-magenta))]/20 hover:shadow-[0_0_14px_rgba(255,46,99,0.4)]",
        outline:
          "border border-[hsl(var(--primary))]/40 bg-transparent text-foreground hover:border-[hsl(var(--primary))]/80 hover:text-[hsl(var(--primary))] hover:shadow-[0_0_12px_rgba(0,255,245,0.25)]",
        secondary:
          "bg-secondary text-secondary-foreground border border-border hover:border-[hsl(var(--primary))]/50 hover:shadow-[0_0_10px_rgba(0,255,245,0.2)]",
        ghost: "text-muted-foreground hover:bg-white/5 hover:text-foreground",
        link: "text-[hsl(var(--primary))] underline-offset-4 hover:underline normal-case tracking-normal",
      },
      size: {
        default: "h-9 px-4 py-2",
        sm: "h-8 px-3 text-xs",
        lg: "h-10 px-8",
        icon: "h-9 w-9",
      },
    },
    defaultVariants: {
      variant: "default",
      size: "default",
    },
  }
)

const Button = React.forwardRef(({ className, variant, size, asChild = false, ...props }, ref) => {
  const Comp = asChild ? Slot : "button"
  return (
    <Comp
      className={cn(buttonVariants({ variant, size, className }))}
      ref={ref}
      {...props} />
  );
})
Button.displayName = "Button"

export { Button, buttonVariants }
