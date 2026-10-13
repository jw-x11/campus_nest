export const priceTypeMeta = {
  single: { unit: 'flat', label: 'One-time' },
  recurring_per_month: { unit: '/mo', label: 'Monthly' },
  recurring_per_week: { unit: '/wk', label: 'Weekly' },
};

export const spaceTypes = ['Closet', 'Shelf', 'Garage', 'Basement', 'Room'];

export const formPriceTypes = [
  { value: 'recurring_per_month', label: 'Per month', hint: 'Billed monthly' },
  { value: 'recurring_per_week', label: 'Per week', hint: 'Flexible short stays' },
  { value: 'single', label: 'One-time', hint: 'Single flat price' },
];

export const bookingStatuses = [
  { value: 'pending', label: 'Pending' },
  { value: 'accepted', label: 'Accepted' },
  { value: 'confirmed', label: 'Confirmed' },
  { value: 'active', label: 'Active' },
  { value: 'completed', label: 'Completed' },
  { value: 'ended', label: 'Ended' },
];

export const statusTone = {
  pending: 'bg-amber-100 text-amber-800',
  accepted: 'bg-sky-100 text-sky-800',
  confirmed: 'bg-emerald-100 text-emerald-800',
  active: 'bg-emerald-100 text-emerald-800',
  completed: 'bg-stone-200 text-stone-600',
  cancelled: 'bg-stone-200 text-stone-500',
  declined: 'bg-red-100 text-red-700',
  ended: 'bg-stone-200 text-stone-500',
};

export const US_STATES = [
  ['AL', 'Alabama'], ['AK', 'Alaska'], ['AZ', 'Arizona'], ['AR', 'Arkansas'], ['CA', 'California'],
  ['CO', 'Colorado'], ['CT', 'Connecticut'], ['DE', 'Delaware'],
  ['FL', 'Florida'], ['GA', 'Georgia'], ['HI', 'Hawaii'], ['ID', 'Idaho'], ['IL', 'Illinois'],
  ['IN', 'Indiana'], ['IA', 'Iowa'], ['KS', 'Kansas'], ['KY', 'Kentucky'], ['LA', 'Louisiana'],
  ['ME', 'Maine'], ['MD', 'Maryland'], ['MA', 'Massachusetts'], ['MI', 'Michigan'], ['MN', 'Minnesota'],
  ['MS', 'Mississippi'], ['MO', 'Missouri'], ['MT', 'Montana'], ['NE', 'Nebraska'], ['NV', 'Nevada'],
  ['NH', 'New Hampshire'], ['NJ', 'New Jersey'], ['NM', 'New Mexico'], ['NY', 'New York'],
  ['NC', 'North Carolina'], ['ND', 'North Dakota'], ['OH', 'Ohio'], ['OK', 'Oklahoma'], ['OR', 'Oregon'],
  ['PA', 'Pennsylvania'], ['RI', 'Rhode Island'], ['SC', 'South Carolina'], ['SD', 'South Dakota'],
  ['TN', 'Tennessee'], ['TX', 'Texas'], ['UT', 'Utah'], ['VT', 'Vermont'], ['VA', 'Virginia'],
  ['WA', 'Washington'], ['DC', 'Washington DC'], ['WV', 'West Virginia'], ['WI', 'Wisconsin'], ['WY', 'Wyoming'],
].map(([value, label]) => ({ value, label }));

/**
 * The two-letter code for a saved state, which may have been typed as "California" or "ca".
 * Returns '' for an empty value and the trimmed text when it is not a US state.
 */
export function stateCode(value) {
  const text = (value || '').trim();
  if (!text) return '';
  const lower = text.toLowerCase();
  if (lower === 'district of columbia') return 'DC';
  const match = US_STATES.find((s) => s.value.toLowerCase() === lower || s.label.toLowerCase() === lower);
  return match ? match.value : text;
}
