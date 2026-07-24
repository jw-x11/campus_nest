// ============================================================
// Campus Nest — sample data
// Lifted from the Campus Nest wireframe logic. Stands in for the
// `spaces`, `bookings`, `reviews`, `conversations` tables until a
// backend is wired up.
// ============================================================

export const ACCENT = '#ffd22e';

export const priceTypeMeta = {
  single: { unit: 'flat', label: 'One-time' },
  recurring_per_month: { unit: '/mo', label: 'Monthly' },
  recurring_per_week: { unit: '/wk', label: 'Weekly' },
};

const rawListings = [
  {
    id: 'walkin-closet-north',
    title: 'Walk-in closet, North Side',
    typeLabel: 'Closet',
    price: 45,
    priceType: 'recurring_per_month',
    dist: '0.3 mi',
    size: '6×4 ft',
    rating: '4.9',
    reviews: 32,
    verified: true,
    accessLabel: 'Self-serve',
    amenities: ['Lockable', 'Ground floor'],
  },
  {
    id: 'dry-garage-bay',
    title: 'Dry garage bay',
    typeLabel: 'Garage',
    price: 80,
    priceType: 'recurring_per_month',
    dist: '0.8 mi',
    size: '10×10 ft',
    rating: '4.8',
    reviews: 21,
    verified: true,
    accessLabel: 'Self-serve',
    amenities: ['Drive-up', '24/7'],
  },
  {
    id: 'lockable-spare-room',
    title: 'Lockable spare room',
    typeLabel: 'Room',
    price: 120,
    priceType: 'recurring_per_month',
    dist: '1.2 mi',
    size: '11×10 ft',
    rating: '5.0',
    reviews: 14,
    verified: true,
    accessLabel: 'Host access',
    amenities: ['Climate', 'Lockable'],
  },
  {
    id: 'basement-corner',
    title: 'Basement corner',
    typeLabel: 'Basement',
    price: 35,
    priceType: 'recurring_per_week',
    dist: '0.5 mi',
    size: '8×6 ft',
    rating: '4.7',
    reviews: 9,
    verified: false,
    accessLabel: 'Self-serve',
    amenities: ['Climate'],
  },
  {
    id: 'shelf-tidy-apartment',
    title: 'Shelf in tidy apartment',
    typeLabel: 'Shelf',
    price: 18,
    priceType: 'recurring_per_week',
    dist: '0.2 mi',
    size: '3×2 ft',
    rating: '4.9',
    reviews: 41,
    verified: true,
    accessLabel: 'Host access',
    amenities: ['Indoor'],
  },
  {
    id: 'hallway-closet',
    title: 'Hallway closet',
    typeLabel: 'Closet',
    price: 28,
    priceType: 'single',
    dist: '0.4 mi',
    size: '4×3 ft',
    rating: '4.8',
    reviews: 18,
    verified: true,
    accessLabel: 'Self-serve',
    amenities: ['Lockable'],
  },
];

export const listings = rawListings.map((l) => ({
  ...l,
  priceUnit: priceTypeMeta[l.priceType].unit,
  priceTypeLabel: priceTypeMeta[l.priceType].label,
}));

export const getListing = (id) =>
  listings.find((l) => l.id === id) || listings[0];

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

export const initialTypeFilters = [
  { label: 'Closet', active: true },
  { label: 'Shelf', active: false },
  { label: 'Garage', active: true },
  { label: 'Basement', active: false },
  { label: 'Room', active: false },
];

export const initialPriceTypeFilters = [
  { label: 'Monthly', active: true, key: 'recurring_per_month' },
  { label: 'Weekly', active: false, key: 'recurring_per_week' },
  { label: 'One-time', active: false, key: 'single' },
];

export const formPriceTypes = [
  { label: 'Per month', sub: 'recurring_per_month' },
  { label: 'Per week', sub: 'recurring_per_week' },
  { label: 'One-time', sub: 'single' },
];

export const amenityOpts = [
  { label: 'Climate-controlled', on: true },
  { label: 'Lockable', on: true },
  { label: 'Ground floor', on: false },
  { label: '24/7 access', on: false },
  { label: 'Drive-up', on: false },
  { label: 'Indoor', on: true },
];

export const detailAmenities = ['Climate-controlled', 'Lockable', 'Ground floor', 'Indoor'];

export const detailReviews = [
  { name: 'Maya R.', when: '2 weeks ago', rating: '★★★★★', initials: 'MR' },
  { name: 'Devon K.', when: '1 month ago', rating: '★★★★★', initials: 'DK' },
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

export const mapPins = [
  { price: '$45', x: 34, y: 38, selected: true },
  { price: '$80', x: 58, y: 30, selected: false },
  { price: '$18', x: 22, y: 62, selected: false },
  { price: '$120', x: 71, y: 55, selected: false },
  { price: '$35', x: 46, y: 70, selected: false },
  { price: '$28', x: 62, y: 74, selected: false },
];

export const profile = {
  name: 'John Doe',
  school: "UC Berkeley · Class of '27",
  memberSince: 'Member since May 2026',
  university: 'UC Berkeley',
  bio: "Junior studying mechanical engineering. I rent out a couple of secure closets and a garage bay near North Side over the summer. Quick to respond, flexible on drop-off times, and I keep everything clean and dry.",
  stats: [
    { num: '3', label: 'Active listings' },
    { num: '47', label: 'Bookings hosted' },
    { num: '4.9', label: 'Avg rating' },
  ],
  reviews: [
    { name: 'Aisha L.', when: '2 weeks ago', rating: '★★★★★', initials: 'AL', role: 'Renter' },
    { name: 'Tom M.', when: '1 month ago', rating: '★★★★★', initials: 'TM', role: 'Renter' },
    { name: 'Priya S.', when: '2 months ago', rating: '★★★★☆', initials: 'PS', role: 'Renter' },
  ],
};

export const savedNotes = [
  'Price dropped $5',
  'Available your dates',
  '2 others saved this',
  'Booked Aug — back soon',
];
