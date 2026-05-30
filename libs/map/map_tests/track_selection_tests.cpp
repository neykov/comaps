#include "testing/testing.hpp"

#include "map/bookmark_manager.hpp"

#include "kml/types.hpp"

#include "base/strings_bundle.hpp"

#include "geometry/point2d.hpp"
#include "geometry/rect2d.hpp"

namespace
{
// Minimal callbacks for a stand-alone BookmarkManager (no persistence / UI), mirroring the bookmark sort tests.
BookmarkManager::Callbacks MakeCallbacks()
{
  return {[]() -> StringsBundle const &
          {
            static StringsBundle const dummyBundle;
            return dummyBundle;
          },
          static_cast<BookmarkManager::Callbacks::GetSeacrhAPIFn>(nullptr),
          static_cast<BookmarkManager::Callbacks::CreatedBookmarksCallback>(nullptr),
          static_cast<BookmarkManager::Callbacks::UpdatedBookmarksCallback>(nullptr),
          static_cast<BookmarkManager::Callbacks::DeletedBookmarksCallback>(nullptr),
          static_cast<BookmarkManager::Callbacks::AttachedBookmarksCallback>(nullptr),
          static_cast<BookmarkManager::Callbacks::DetachedBookmarksCallback>(nullptr)};
}

// Adds a horizontal track spanning x in [0, 1] at the given y, attached to cat, and returns its id.
kml::TrackId AddHorizontalTrack(BookmarkManager::EditSession & es, kml::MarkGroupId cat, double y)
{
  kml::TrackData trackData;
  trackData.m_geometry.AddLine({{{0.0, y}, 0}, {{1.0, y}, 0}});
  trackData.m_geometry.AddTimestamps({});
  auto const * track = es.CreateTrack(std::move(trackData));
  es.AttachTrack(track->GetId(), cat);
  return track->GetId();
}
}  // namespace

// Verifies that FindTracksInTapPosition collects every visible track under the tap rect and returns them
// sorted nearest-first - the building block for disambiguating overlapping/close tracks on tap.
UNIT_TEST(BookmarkManager_FindTracksInTapPosition)
{
  BookmarkManager bmManager(MakeCallbacks());

  auto const cat = bmManager.CreateBookmarkCategory("test", false /* autoSave */);

  kml::TrackId t0, t1, t2;
  {
    auto es = bmManager.GetEditSession();
    es.SetIsVisible(cat, true);
    // Three parallel horizontal tracks at increasing distance from y = 0.
    t0 = AddHorizontalTrack(es, cat, 0.0);
    t1 = AddHorizontalTrack(es, cat, 0.001);
    t2 = AddHorizontalTrack(es, cat, 0.010);
  }
  UNUSED_VALUE(t2);

  // Tap rect centered at (0.5, 0.0) with half-size 0.002 intersects t0 and t1 but not t2.
  m2::RectD const touchRect(0.5 - 0.002, -0.002, 0.5 + 0.002, 0.002);
  auto const candidates = bmManager.FindTracksInTapPosition(touchRect);

  TEST_EQUAL(candidates.size(), 2, ("Only the two tracks under the tap should be returned"));
  TEST_EQUAL(candidates[0].m_trackId, t0, ("The nearest track must come first"));
  TEST_EQUAL(candidates[1].m_trackId, t1, ());
  TEST_LESS(candidates[0].m_squareDist, candidates[1].m_squareDist, ("Candidates must be sorted by ascending distance"));

  // A tap far from every track returns nothing.
  m2::RectD const emptyRect(0.5 - 0.0001, 0.5 - 0.0001, 0.5 + 0.0001, 0.5 + 0.0001);
  TEST(bmManager.FindTracksInTapPosition(emptyRect).empty(), ("No tracks are close to this tap"));
}
