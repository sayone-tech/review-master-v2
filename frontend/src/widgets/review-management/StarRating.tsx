import { Star } from "lucide-react";

interface Props {
  rating: 1 | 2 | 3 | 4 | 5;
}

export function StarRating({ rating }: Props) {
  return (
    <span
      className="inline-flex items-center gap-1"
      aria-label={`${rating} out of 5 stars`}
    >
      {[1, 2, 3, 4, 5].map((n) => (
        <Star
          key={n}
          size={14}
          className={n <= rating ? "text-yellow fill-current" : "text-line fill-current"}
          aria-hidden="true"
        />
      ))}
    </span>
  );
}
