export const ACCENT = '#ffd22e';

export const priceTypeMeta = {
  single: { unit: 'flat', label: 'One-time' },
  recurring_per_month: { unit: '/mo', label: 'Monthly' },
  recurring_per_week: { unit: '/wk', label: 'Weekly' },
};

export const spaceTypes = ['Closet', 'Shelf', 'Garage', 'Basement', 'Room', 'Other'];

export const valueProps = [
  { icon: '$', title: 'Up to 70% cheaper', body: 'Skip the $200/mo commercial unit.' },
  { icon: '⌖', title: 'Steps from campus', body: 'Most spaces under a mile away.' },
  { icon: '▦', title: 'Rent by the week', body: 'No month-long minimums or contracts.' },
];

export const stepsRenter = [
  { num: '01', title: 'Search nearby', body: 'Filter by area, dates, size and price.' },
  { num: '02', title: 'Request the dates', body: 'Message the host and lock your window.' },
  { num: '03', title: 'Drop off & store', body: 'Self-serve or host-accompanied access.' },
];

export const stepsLister = [
  { num: '01', title: 'List your space', body: 'A closet, shelf, garage or spare room.' },
  { num: '02', title: 'Approve a renter', body: 'You approve every booking request.' },
  { num: '03', title: 'Earn each month', body: 'Get paid directly, no commission in MVP.' },
];

export const formPriceTypes = [
  { label: 'Per month', sub: 'recurring_per_month' },
  { label: 'Per week', sub: 'recurring_per_week' },
  { label: 'One-time', sub: 'single' },
];

export const conversations = [
  { id: 'aisha', initials: 'AL', name: 'Aisha L.', space: 'Walk-in closet, North Side', snippet: 'Sounds good — I can do the 1st.', when: '2m', unread: 2, rating: '4.8', pending: true },
  { id: 'tom', initials: 'TM', name: 'Tom M.', space: 'Dry garage bay', snippet: 'Is the space climate controlled?', when: '1h', unread: 0, rating: '4.9', pending: false },
  { id: 'priya', initials: 'PS', name: 'Priya S.', space: 'Lockable spare room', snippet: 'Thanks! See you Saturday.', when: '3h', unread: 0, rating: '5.0', pending: false },
  { id: 'jordan', initials: 'JC', name: 'Jordan C.', space: 'Basement corner', snippet: 'Booking request sent', when: '1d', unread: 0, rating: '4.7', pending: true },
];

export const threadMessages = [
  { mine: false, text: 'Hi! Is the walk-in closet still available June through August?', when: '9:02 AM' },
  { mine: true, text: 'Hey Aisha! Yes it is — self-serve access, lockable door. When would you want to drop off?', when: '9:05 AM' },
  { mine: false, text: 'Perfect. I have about 8 boxes and a bike. Would that fit?', when: '9:07 AM' },
  { mine: true, text: 'Should be plenty of room for that. The bike can hang on the wall hook.', when: '9:09 AM' },
  { mine: false, text: 'Sounds good — I can do the 1st.', when: '9:11 AM' },
];
