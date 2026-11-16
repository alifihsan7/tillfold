import { useRef } from "react";

/**
 * Ref that always holds the latest value. Lets an effect call the current
 * version of a callback without re-running every time the callback is
 * recreated, and without capturing a stale closure.
 */
export function useLatest<T>(value: T) {
  const ref = useRef(value);
  ref.current = value;
  return ref;
}
