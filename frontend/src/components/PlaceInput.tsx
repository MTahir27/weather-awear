import { useQuery } from '@tanstack/react-query'
import { useId, useState, type KeyboardEvent } from 'react'

import { searchPlaces } from '../api/client'
import type { Place } from '../api/schemas'
import { useDebouncedValue } from '../hooks/useDebouncedValue'

const MIN_QUERY_LENGTH = 2
const DEBOUNCE_MS = 300

interface PlaceInputProps {
  label: string
  value: Place | null
  onChange: (place: Place | null) => void
  error?: string
  placeholder?: string
}

/** Place search box following the WAI-ARIA combobox pattern. */
export function PlaceInput({ label, value, onChange, error, placeholder }: PlaceInputProps) {
  const id = useId()
  const listId = `${id}-options`
  const errorId = `${id}-error`
  const [text, setText] = useState(value?.label ?? '')
  const [open, setOpen] = useState(false)
  const [active, setActive] = useState(-1)

  const query = useDebouncedValue(text.trim(), DEBOUNCE_MS)
  const searching = open && !value && query.length >= MIN_QUERY_LENGTH
  const {
    data: places = [],
    isFetching,
    isError,
  } = useQuery({
    queryKey: ['places', query.toLowerCase()],
    queryFn: ({ signal }) => searchPlaces(query, signal),
    enabled: searching,
    staleTime: 60 * 60 * 1000,
  })
  const options = searching ? places : []
  const expanded = open && options.length > 0

  const select = (place: Place) => {
    onChange(place)
    setText(place.label)
    setOpen(false)
    setActive(-1)
  }

  const onKeyDown = (event: KeyboardEvent<HTMLInputElement>) => {
    if (event.key === 'ArrowDown' && options.length) {
      event.preventDefault()
      setOpen(true)
      setActive((i) => (i + 1) % options.length)
    } else if (event.key === 'ArrowUp' && options.length) {
      event.preventDefault()
      setActive((i) => (i <= 0 ? options.length - 1 : i - 1))
    } else if (event.key === 'Enter' && expanded) {
      event.preventDefault()
      const place = options[active >= 0 ? active : 0]
      if (place) select(place)
    } else if (event.key === 'Escape') {
      setOpen(false)
      setActive(-1)
    }
  }

  const status =
    searching && isFetching
      ? 'Searching…'
      : searching && isError
        ? 'Place search is unavailable right now.'
        : searching && !isFetching && options.length === 0
          ? 'No matching places in the US or Canada.'
          : null

  return (
    <div className="relative">
      <label htmlFor={id} className="mb-1 block text-sm font-medium text-slate-700">
        {label}
      </label>
      <input
        id={id}
        type="text"
        role="combobox"
        autoComplete="off"
        aria-autocomplete="list"
        aria-expanded={expanded}
        aria-controls={listId}
        aria-activedescendant={expanded && active >= 0 ? `${listId}-${active}` : undefined}
        aria-invalid={Boolean(error)}
        aria-describedby={error ? errorId : undefined}
        placeholder={placeholder}
        value={text}
        onChange={(event) => {
          setText(event.target.value)
          setOpen(true)
          setActive(-1)
          if (value) onChange(null)
        }}
        onFocus={() => setOpen(true)}
        onBlur={() => setOpen(false)}
        onKeyDown={onKeyDown}
        className={`w-full rounded-lg border bg-white px-3 py-2 text-sm shadow-sm outline-none focus:ring-2 focus:ring-sky-500 ${
          error ? 'border-red-500' : 'border-slate-300'
        }`}
      />
      <ul
        id={listId}
        role="listbox"
        aria-label={`${label} suggestions`}
        hidden={!expanded}
        className="absolute z-20 mt-1 max-h-64 w-full overflow-auto rounded-lg border border-slate-200 bg-white py-1 shadow-lg"
      >
        {options.map((place, index) => (
          <li
            key={`${place.label}-${place.lat}-${place.lon}`}
            id={`${listId}-${index}`}
            role="option"
            aria-selected={index === active}
            // Keep focus in the input so blur does not close the list before the click lands.
            onMouseDown={(event) => event.preventDefault()}
            onClick={() => select(place)}
            className={`cursor-pointer px-3 py-2 text-sm ${
              index === active ? 'bg-sky-100' : 'hover:bg-slate-100'
            }`}
          >
            {place.label}
          </li>
        ))}
      </ul>
      {status && open && (
        <p className="mt-1 text-xs text-slate-500" role="status">
          {status}
        </p>
      )}
      {error && (
        <p id={errorId} className="mt-1 text-xs text-red-600">
          {error}
        </p>
      )}
    </div>
  )
}
