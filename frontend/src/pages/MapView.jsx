import { useEffect, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import { SearchIcon } from '../components/icons.jsx';
import { SpaceRow } from '../components/cards.jsx';
import SpaceMap from '../components/SpaceMap.jsx';
import { LoadingState, ErrorState, EmptyState } from '../components/ui.jsx';
import { MAX_PIN_SPAN_DEG, boundsSpan, formatPrice, getSpacePins, searchSpaces } from '../api.js';

// Where the map starts when the user does not share their location.
const GOLETA = { latitude: 34.4358, longitude: -119.8276, zoom: 12 };
const USER_ZOOM = 14;
// If the browser's permission prompt is ignored, show Goleta rather than an empty map.
const LOCATION_WAIT_MS = 10000;
const PAGE_SIZE = 25;
// Search this long after the user stops panning or zooming.
const SEARCH_DELAY_MS = 500;
// The server stops counting matches here, so a total this high means "at least".
const MAX_COUNTED = 500;

const countLabel = (count) => `${count}${count >= MAX_COUNTED ? '+' : ''}`;

const contains = (outer, inner) =>
  inner.south >= outer.south && inner.north <= outer.north && inner.west >= outer.west && inner.east <= outer.east;

export default function MapView() {
  // Cards in the side list, one page at a time.
  const [spaces, setSpaces] = useState([]);
  const [total, setTotal] = useState(0);
  const [hasMore, setHasMore] = useState(false);
  const [page, setPage] = useState(1);
  const [listState, setListState] = useState('loading');
  // A new search is running while the previous results stay on screen.
  const [refreshing, setRefreshing] = useState(false);
  const [loadingMore, setLoadingMore] = useState(false);
  // Pins on the map: every listing in the searched area, up to the server's limit.
  const [pins, setPins] = useState([]);
  const [pinTotal, setPinTotal] = useState(0);
  const [truncated, setTruncated] = useState(false);
  const [pinsFailed, setPinsFailed] = useState(false);

  const [selectedId, setSelectedId] = useState(null);
  // Card under the mouse, so its pin can stand out on the map.
  const [hoveredId, setHoveredId] = useState(null);
  const [scrollTarget, setScrollTarget] = useState(null);
  // Phones show the list as a sheet over the map, closed until asked for. Wide screens always show it.
  const [listOpen, setListOpen] = useState(false);
  const [focus, setFocus] = useState(null);
  // null until we know where to start: the user's position, or Goleta.
  const [view, setView] = useState(() => ('geolocation' in navigator ? null : GOLETA));
  // The area on screen now, and the area the results are for.
  const [currentBounds, setCurrentBounds] = useState(null);
  const [searchedBounds, setSearchedBounds] = useState(null);

  // Responses to a search that has since been replaced are dropped.
  const searchId = useRef(0);
  // Search by itself once the map has settled: when it opens, and after it flies to the user.
  const searchOnNextMove = useRef(true);
  // Pending search after the user's last pan or zoom.
  const searchTimer = useRef(null);

  const tooLarge = currentBounds != null && boundsSpan(currentBounds) > MAX_PIN_SPAN_DEG;

  const runSearch = (bounds) => {
    clearTimeout(searchTimer.current);
    const id = ++searchId.current;
    setSearchedBounds(bounds);
    // Keep the current results on screen while the new ones load, so the list does not flash.
    setListState((current) => (current === 'ready' ? 'ready' : 'loading'));
    setRefreshing(true);
    setPinsFailed(false);

    searchSpaces({ bounds, page: 1, pageSize: PAGE_SIZE, sortBy: 'post_date', sortOrder: 'desc' })
      .then((data) => {
        if (id !== searchId.current) return;
        setSpaces(data.spaces);
        setTotal(data.total);
        setHasMore(data.hasMore);
        setPage(1);
        setListState('ready');
      })
      .catch(() => {
        if (id === searchId.current) setListState('error');
      })
      .finally(() => {
        if (id === searchId.current) setRefreshing(false);
      });

    // Zoomed out past a city, the list still updates but pins are not searched.
    if (boundsSpan(bounds) > MAX_PIN_SPAN_DEG) {
      setPins([]);
      setPinTotal(0);
      setTruncated(false);
      return;
    }
    getSpacePins(bounds)
      .then((data) => {
        if (id !== searchId.current) return;
        setPins(data.pins);
        setPinTotal(data.total);
        setTruncated(data.truncated);
      })
      .catch(() => {
        if (id === searchId.current) setPinsFailed(true);
      });
  };

  const loadMore = () => {
    const id = searchId.current;
    setLoadingMore(true);
    searchSpaces({ bounds: searchedBounds, page: page + 1, pageSize: PAGE_SIZE, sortBy: 'post_date', sortOrder: 'desc' })
      .then((data) => {
        if (id !== searchId.current) return;
        setSpaces((current) => [...current, ...data.spaces]);
        setHasMore(data.hasMore);
        setPage((current) => current + 1);
      })
      .catch(() => {})
      .finally(() => setLoadingMore(false));
  };

  const handleBoundsChange = (bounds, byUser) => {
    setCurrentBounds(bounds);
    if (searchOnNextMove.current) {
      searchOnNextMove.current = false;
      runSearch(bounds);
    } else if (byUser) {
      // Zooming to a selected listing moves the map too, but should not replace the results.
      clearTimeout(searchTimer.current);
      // Zoomed out past a city, nothing is searched: the last results stay, grayed out.
      if (boundsSpan(bounds) > MAX_PIN_SPAN_DEG) return;
      // Zoomed in within the area already searched, the pins on screen are already every
      // listing there. Search again only if that search left pins out or did not finish.
      const complete =
        searchedBounds != null &&
        boundsSpan(searchedBounds) <= MAX_PIN_SPAN_DEG &&
        listState === 'ready' &&
        !truncated &&
        !pinsFailed;
      if (complete && contains(searchedBounds, bounds)) return;
      searchTimer.current = setTimeout(() => runSearch(bounds), SEARCH_DELAY_MS);
    }
  };

  // A pan or zoom that starts again within the delay waits for the user to stop once more.
  const handleMoveStart = () => clearTimeout(searchTimer.current);

  useEffect(() => () => clearTimeout(searchTimer.current), []);

  // Ask for the user's location as soon as the page opens. A refusal or a failure means Goleta.
  useEffect(() => {
    if (!('geolocation' in navigator)) return undefined;
    const giveUp = setTimeout(() => setView((current) => current ?? GOLETA), LOCATION_WAIT_MS);
    navigator.geolocation.getCurrentPosition(
      (position) =>
        setView({
          latitude: position.coords.latitude,
          longitude: position.coords.longitude,
          zoom: USER_ZOOM,
        }),
      () => setView((current) => current ?? GOLETA),
      { timeout: LOCATION_WAIT_MS, maximumAge: 5 * 60 * 1000 },
    );
    return () => clearTimeout(giveUp);
  }, []);

  // When the location arrives after the map opened, the map flies there; search where it lands.
  useEffect(() => {
    if (view && searchId.current > 0) searchOnNextMove.current = true;
  }, [view]);

  const shownPins = tooLarge ? [] : pins;
  // A pin may be selected whose card is on a later page, so fall back to the pin itself.
  const selectedItem = spaces.find((s) => s.id === selectedId) ?? pins.find((p) => p.id === selectedId);

  // Highlight a listing and zoom the map to its pin. A listing with no coordinates is only highlighted.
  const select = (item) => {
    setSelectedId(item.id);
    if (item.latitude != null && item.longitude != null) {
      // A new object every time, so choosing the same listing again zooms back to it.
      setFocus({ latitude: item.latitude, longitude: item.longitude });
    }
  };

  const selectOnMap = (id) => {
    const item = spaces.find((s) => s.id === id) ?? pins.find((p) => p.id === id);
    if (!item) return;
    // The pin is already on screen, so the map stays where the user put it.
    setSelectedId(item.id);
    // On a phone the list may be closed; open it and bring the card into view once it renders.
    setListOpen(true);
    setScrollTarget({ id: item.id });
  };

  // A new object each time, so clicking the same pin again scrolls back to its card.
  useEffect(() => {
    if (!scrollTarget) return;
    document
      .getElementById(`map-card-${scrollTarget.id}`)
      ?.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
  }, [scrollTarget]);

  return (
    <div className="mx-auto w-full max-w-[1320px] px-4 pb-16 pt-6 sm:px-5">
      <div className="card overflow-hidden">
        <div className="flex flex-wrap items-center gap-3 border-b border-stone-100 px-4 py-3">
          <span className="flex min-w-0 flex-1 items-center gap-2 text-sm text-stone-500">
            <SearchIcon size={15} /> Map of listed spaces
          </span>
          <span className="font-mono text-xs text-stone-400">
            {tooLarge
              ? 'Zoom in to update the list'
              : `${countLabel(total)} spaces in this area · showing ${spaces.length}`}
          </span>
          <div className="flex overflow-hidden rounded-full border border-stone-200 text-[13px]">
            <Link to="/search" className="px-4 py-1.5 text-stone-500 hover:bg-stone-50">List</Link>
            <span className="bg-[#2b2b2b] px-4 py-1.5 font-semibold text-white">Map</span>
          </div>
        </div>

        <div className="relative grid lg:grid-cols-[380px_1fr]">
          <div
            className={`${listOpen ? 'flex' : 'hidden'} absolute inset-x-0 bottom-0 z-10 max-h-[60%] flex-col rounded-t-2xl bg-white shadow-[0_-8px_24px_rgba(0,0,0,0.12)] lg:static lg:flex lg:max-h-[560px] lg:rounded-none lg:border-r lg:border-stone-100 lg:shadow-none`}
          >
            <div className="flex flex-none items-center justify-between border-b border-stone-100 px-4 py-2 lg:hidden">
              <span className="font-mono text-xs text-stone-400">
                {tooLarge ? 'Zoom in to update the list' : `${countLabel(total)} spaces in this area`}
              </span>
              <button onClick={() => setListOpen(false)} className="btn btn-sm">
                Hide list
              </button>
            </div>
            <div className="min-h-0 flex-1 overflow-y-auto">
              {listState === 'loading' && <LoadingState label="Loading spaces…" />}
              {listState === 'error' && (
                <ErrorState message="Could not load spaces." onRetry={() => searchedBounds && runSearch(searchedBounds)} />
              )}
              {listState === 'ready' && spaces.length === 0 && (
                <EmptyState title="No spaces here" body="Zoom out or move the map to look somewhere else." />
              )}
              {listState === 'ready' &&
                spaces.map((item) => (
                  <div
                    key={item.id}
                    id={`map-card-${item.id}`}
                    // Zoomed out, these are the results for an earlier area, so they are grayed out.
                    aria-disabled={tooLarge || undefined}
                    onMouseEnter={() => setHoveredId(item.id)}
                    onMouseLeave={() => setHoveredId((current) => (current === item.id ? null : current))}
                    className={`border-b border-stone-100 transition last:border-0 ${
                      tooLarge
                        ? 'pointer-events-none opacity-40 grayscale'
                        : item.id === selectedId
                          ? 'bg-amber-100/70 shadow-[inset_4px_0_0_#ffd22e]'
                          : ''
                    }`}
                  >
                    <SpaceRow item={item} onClick={() => select(item)} hoverable={false} />
                  </div>
                ))}
              {listState === 'ready' && hasMore && !tooLarge && (
                <div className="flex justify-center p-4">
                  <button onClick={loadMore} disabled={loadingMore} className="btn btn-sm">
                    {loadingMore ? 'Loading…' : 'Load more'}
                  </button>
                </div>
              )}
            </div>
          </div>

          <div className="relative h-[70vh] min-h-[420px] overflow-hidden bg-[#ecebe4] lg:h-auto lg:min-h-[560px]">
            <div className="absolute inset-0">
              {view ? (
                <SpaceMap
                  pins={shownPins}
                  selectedId={selectedId}
                  hoveredId={hoveredId}
                  view={view}
                  focus={focus}
                  onSelect={selectOnMap}
                  onBoundsChange={handleBoundsChange}
                  onMoveStart={handleMoveStart}
                />
              ) : (
                <LoadingState label="Finding your location…" />
              )}
            </div>

            {tooLarge && (
              <div className="pointer-events-none absolute inset-0 z-[4] flex items-center justify-center">
                <p className="card px-4 py-2 text-sm font-semibold shadow-lg !rounded-full">Zoom in to show pins</p>
              </div>
            )}

            {!tooLarge && (truncated || pinsFailed) && (
              <p className="card absolute left-1/2 top-14 z-[5] -translate-x-1/2 whitespace-nowrap px-3 py-1 text-xs text-stone-600 shadow-md !rounded-full">
                {pinsFailed
                  ? 'Could not load pins'
                  : `Showing ${pins.length} of ${countLabel(pinTotal)} — zoom in for all`}
              </p>
            )}

            {!listOpen && (
              // lg:hidden sits on a wrapper because .btn sets display outside Tailwind's layers and would win.
              <div className="absolute bottom-4 right-4 z-[6] lg:hidden">
                <button onClick={() => setListOpen(true)} className="btn btn-sm shadow-md">
                  ☰ List · {countLabel(total)}
                </button>
              </div>
            )}

            {selectedItem && !tooLarge && (
              // On a phone the open list covers this corner and already shows the listing.
              <div
                className={`card absolute bottom-4 left-4 z-[5] w-60 p-3 !rounded-2xl shadow-lg ${listOpen ? 'hidden lg:block' : ''}`}
              >
                <p className="truncate text-sm font-semibold">{selectedItem.title}</p>
                {selectedItem.viewCount != null && (
                  <p className="mt-0.5 font-mono text-[11px] text-stone-400">
                    {selectedItem.location || '—'} · {selectedItem.viewCount} views
                  </p>
                )}
                <p className="display mt-1">
                  ${formatPrice(selectedItem.price)}
                  <span className="text-xs font-normal text-stone-400">{selectedItem.priceUnit}</span>
                </p>
                <Link
                  to={`/space/${selectedItem.id}`}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="btn btn-sm btn-dark mt-3 w-full justify-center"
                >
                  Show details
                </Link>
              </div>
            )}

            {refreshing && listState === 'ready' && (
              <p className="card pointer-events-none absolute left-1/2 top-4 z-[5] flex -translate-x-1/2 items-center gap-2 px-3 py-1.5 text-xs text-stone-600 shadow-md !rounded-full">
                <span className="inline-block h-3 w-3 animate-spin rounded-full border-2 border-stone-300 border-t-stone-600" />
                Updating…
              </p>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
