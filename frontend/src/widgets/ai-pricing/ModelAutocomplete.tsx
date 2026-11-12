import { useEffect, useId, useRef, useState } from "react";
import { fetchSuggestions } from "./api";
import type { ModelSuggestion } from "./types";

interface Props {
  id: string;
  value: string;
  onChange: (value: string) => void;
  "aria-describedby"?: string;
  "aria-invalid"?: boolean;
}

const DEBOUNCE_MS = 200;

/** Free-text model input with server suggestions (unpriced models first). */
export function ModelAutocomplete({ id, value, onChange, ...aria }: Props) {
  const listId = useId();
  const [active, setActive] = useState(false);
  const [options, setOptions] = useState<ModelSuggestion[]>([]);
  const [highlight, setHighlight] = useState(-1);
  const req = useRef(0);

  useEffect(() => {
    if (!active) return;
    const mine = ++req.current;
    const timer = setTimeout(() => {
      fetchSuggestions(value.trim())
        .then((r) => {
          if (mine !== req.current) return;
          // Unpriced first; Array.sort is stable so server order holds within each group.
          setOptions([...r.results].sort((a, b) => Number(a.has_price) - Number(b.has_price)));
          setHighlight(-1);
        })
        .catch(() => {
          if (mine === req.current) setOptions([]);
        });
    }, DEBOUNCE_MS);
    return () => clearTimeout(timer);
  }, [active, value]);

  const open = active && options.length > 0;
  const optionId = (i: number) => `${listId}-opt-${i}`;

  const close = () => {
    req.current++;
    setActive(false);
    setOptions([]);
    setHighlight(-1);
  };

  const select = (model: string) => {
    onChange(model);
    close();
  };

  const onKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "ArrowDown") {
      e.preventDefault();
      if (!active) setActive(true);
      if (options.length > 0) setHighlight((h) => (h + 1) % options.length);
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      if (options.length > 0) setHighlight((h) => (h <= 0 ? options.length - 1 : h - 1));
    } else if (e.key === "Enter" && open) {
      // Never submit the form while the list is open.
      e.preventDefault();
      if (highlight >= 0) select(options[highlight].model);
      else close();
    } else if (e.key === "Escape" && open) {
      e.stopPropagation(); // don't also dismiss the surrounding modal
      close();
    }
  };

  return (
    <div className="relative">
      <input
        id={id}
        role="combobox"
        aria-expanded={open}
        aria-controls={open ? listId : undefined}
        aria-activedescendant={open && highlight >= 0 ? optionId(highlight) : undefined}
        aria-autocomplete="list"
        autoComplete="off"
        type="text"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        onKeyDown={onKeyDown}
        onFocus={() => setActive(true)}
        onBlur={() => {
          req.current++;
          setActive(false);
        }}
        className="w-full px-3 py-2 border border-line rounded-md text-[13.5px] bg-white"
        {...aria}
      />
      {open && (
        <ul
          id={listId}
          role="listbox"
          className="absolute z-10 mt-1 w-full max-h-56 overflow-auto bg-white border border-line rounded-md shadow-lg"
        >
          {options.map((o, i) => (
            <li
              key={o.model}
              id={optionId(i)}
              role="option"
              aria-selected={i === highlight}
              // mousedown (not click) so it fires before the input's blur closes the list
              onMouseDown={(e) => {
                e.preventDefault();
                select(o.model);
              }}
              className={`flex items-center justify-between gap-3 px-3 py-2 text-[13.5px] cursor-pointer hover:bg-line-soft${i === highlight ? " bg-line-soft" : ""}`}
            >
              <span>{o.model}</span>
              {!o.has_price && <span className="text-[12px] text-red">⚠ No pricing</span>}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
