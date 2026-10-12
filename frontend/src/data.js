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
