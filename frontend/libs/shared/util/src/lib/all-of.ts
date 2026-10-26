/**
 * A runtime list of every member of a union type, checked at compile time.
 *
 *   export const CALL_PRIORITIES = allOf<CallPriority>()(['Critical', 'High', 'Normal', 'Low']);
 *
 * If the API adds a value to the union, the call stops compiling and names what is missing.
 */
export function allOf<T>() {
  return <const L extends readonly T[]>(
    listed: L &
      ([Exclude<T, L[number]>] extends [never]
        ? unknown
        : { missing: Exclude<T, L[number]> }),
  ): L => listed;
}
