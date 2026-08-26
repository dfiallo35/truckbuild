import Image from "next/image";

type MediaBlockProps = {
  src: string;
  alt: string;
  caption?: string;
  aspect?: "video" | "square" | "portrait";
  priority?: boolean;
  sizes?: string;
  className?: string;
};

const ASPECT_CLASSES: Record<NonNullable<MediaBlockProps["aspect"]>, string> = {
  video: "aspect-video",
  square: "aspect-square",
  portrait: "aspect-[3/4]",
};

export function MediaBlock({
  src,
  alt,
  caption,
  aspect = "video",
  priority = false,
  sizes = "100vw",
  className = "",
}: MediaBlockProps) {
  return (
    <figure className={className}>
      <div
        className={`border-border bg-canvas-raised relative overflow-hidden border ${ASPECT_CLASSES[aspect]}`}
      >
        <Image
          src={src}
          alt={alt}
          fill
          priority={priority}
          sizes={sizes}
          className="object-cover"
        />
      </div>
      {caption ? (
        <figcaption className="font-data text-ink-faint mt-2 text-xs tracking-widest uppercase">
          {caption}
        </figcaption>
      ) : null}
    </figure>
  );
}
