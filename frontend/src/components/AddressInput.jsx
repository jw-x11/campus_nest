import { useEffect, useId, useRef, useState } from 'react';
import { autocompleteAddress } from '../api.js';

const MIN_CHARS = 3;
const DELAY_MS = 1000;

/**
 * A street-address input that suggests addresses while the user types.
 * onChange gets the typed text. onSelect gets the chosen suggestion
 * ({ address, city, state, postalCode, latitude, longitude }).
 * If suggestions are unavailable the input still works as a plain text field.
 */
export default function AddressInput({ value, onChange, onSelect, placeholder, required }) {
  const listId = useId();
  const [suggestions, setSuggestions] = useState([]);
  const [open, setOpen] = useState(false);
  const [active, setActive] = useState(-1);
  const timer = useRef(null);
  // Bumped on every keystroke and selection, so an answer to an older request is ignored.
  const latest = useRef(0);

  useEffect(() => () => clearTimeout(timer.current), []);

  const close = () => {
    setOpen(false);
    setActive(-1);
  };

  const handleChange = (e) => {
    const text = e.target.value;
    onChange(text);
    clearTimeout(timer.current);
    latest.current += 1;
    const mine = latest.current;
    if (text.trim().length < MIN_CHARS) {
      setSuggestions([]);
      close();
      return;
    }
    timer.current = setTimeout(async () => {
      let found = [];
      try {
        found = await autocompleteAddress(text.trim());
      } catch {
        // Suggestions are a convenience. Typing the address by hand still works.
      }
      if (mine !== latest.current) return;
      setSuggestions(found);
      setActive(-1);
      setOpen(found.length > 0);
    }, DELAY_MS);
  };

  const choose = (suggestion) => {
    clearTimeout(timer.current);
    latest.current += 1;
    setSuggestions([]);
    close();
    onSelect(suggestion);
  };

  const handleKeyDown = (e) => {
    if (!open) return;
    if (e.key === 'ArrowDown') {
      e.preventDefault();
      setActive((i) => (i + 1) % suggestions.length);
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      setActive((i) => (i <= 0 ? suggestions.length - 1 : i - 1));
    } else if (e.key === 'Enter' && active >= 0) {
      // Pick the highlighted suggestion instead of submitting the form.
      e.preventDefault();
      choose(suggestions[active]);
    } else if (e.key === 'Escape') {
      // Close the list only, not an enclosing dialog.
      e.stopPropagation();
      close();
    }
  };

  return (
    <div className="relative">
      <input
        className="input"
        value={value}
        onChange={handleChange}
        onKeyDown={handleKeyDown}
        onBlur={close}
        placeholder={placeholder}
        required={required}
        autoComplete="off"
        role="combobox"
        aria-expanded={open}
        aria-controls={listId}
        aria-autocomplete="list"
        aria-activedescendant={active >= 0 ? `${listId}-${active}` : undefined}
      />
      {open && (
        <ul
          id={listId}
          role="listbox"
          className="absolute left-0 right-0 top-full z-20 mt-1 overflow-hidden rounded-xl border border-stone-200 bg-white py-1 shadow-lg"
        >
          {suggestions.map((s, i) => (
            <li
              key={s.label}
              id={`${listId}-${i}`}
              role="option"
              aria-selected={i === active}
              // mousedown would blur the input and close the list before the click lands.
              onMouseDown={(e) => e.preventDefault()}
              onMouseEnter={() => setActive(i)}
              onClick={(e) => {
                // The input sits inside a <label>, which would otherwise forward this click.
                e.preventDefault();
                choose(s);
              }}
              className={`cursor-pointer px-3.5 py-2 text-sm ${
                i === active ? 'bg-stone-100' : ''
              }`}
            >
              {s.label}
            </li>
          ))}
          <li className="px-3.5 pb-1 pt-1.5 font-mono text-[10.5px] text-stone-400" aria-hidden="true">
            Suggestions by Geoapify · © OpenStreetMap contributors
          </li>
        </ul>
      )}
    </div>
  );
}
