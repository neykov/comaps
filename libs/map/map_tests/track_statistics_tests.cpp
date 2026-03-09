#include "testing/testing.hpp"

#include "map/track_statistics.hpp"

#include "geometry/mercator.hpp"
#include "geometry/point_with_altitude.hpp"

#include "kml/types.hpp"

namespace track_statistics_tests
{
using namespace geometry;
using namespace location;

GpsInfo const BuildGpsInfo(double latitude, double longitude, double altitude, double timestamp = 0)
{
  GpsInfo gpsInfo;
  gpsInfo.m_latitude = latitude;
  gpsInfo.m_longitude = longitude;
  gpsInfo.m_altitude = altitude;
  gpsInfo.m_timestamp = timestamp;
  return gpsInfo;
}

UNIT_TEST(TrackStatistics_EmptyMultiGeometry)
{
  TrackStatistics ts;
  TEST_EQUAL(0, ts.m_ascent, ());
  TEST_EQUAL(0, ts.m_descent, ());
  TEST_EQUAL(ts.m_minElevation, kDefaultAltitudeMeters, ());
  TEST_EQUAL(ts.m_maxElevation, kDefaultAltitudeMeters, ());
}

UNIT_TEST(TrackStatistics_FromMultiGeometry)
{
  kml::MultiGeometry geometry;
  auto const point1 = PointWithAltitude({0.0, 0.0}, 100);
  auto const point2 = PointWithAltitude({1.0, 1.0}, 150);
  auto const point3 = PointWithAltitude({2.0, 2.0}, 50);
  geometry.AddLine({point1, point2, point3});
  geometry.AddTimestamps({0, 1, 2});
  auto const ts = TrackStatistics(geometry);
  TEST_EQUAL(ts.m_minElevation, 50, ());
  TEST_EQUAL(ts.m_maxElevation, 150, ());
  TEST_EQUAL(ts.m_ascent, 50, ());    // Ascent from 100 -> 150
  TEST_EQUAL(ts.m_descent, 100, ());  // Descent from 150 -> 50
  TEST_EQUAL(ts.m_duration, 2, ());

  double distance = 0;
  distance += mercator::DistanceOnEarth(point1, point2);
  distance += mercator::DistanceOnEarth(point2, point3);
  TEST_EQUAL(ts.m_length, distance, ());
}

UNIT_TEST(TrackStatistics_NoAltitudeAndTimestampPoints)
{
  kml::MultiGeometry geometry;
  geometry.AddLine({PointWithAltitude({0.0, 0.0}), PointWithAltitude({1.0, 1.0}), PointWithAltitude({2.0, 2.0})});

  auto const ts = TrackStatistics(geometry);

  TEST_EQUAL(ts.m_minElevation, kDefaultAltitudeMeters, ());
  TEST_EQUAL(ts.m_maxElevation, kDefaultAltitudeMeters, ());
  TEST_EQUAL(ts.m_ascent, 0, ());
  TEST_EQUAL(ts.m_descent, 0, ());
  TEST_EQUAL(ts.m_duration, 0, ());
}

UNIT_TEST(TrackStatistics_MultipleLines)
{
  kml::MultiGeometry geometry;
  geometry.AddLine(
      {PointWithAltitude({0.0, 0.0}, 100), PointWithAltitude({1.0, 1.0}, 150), PointWithAltitude({1.0, 1.0}, 140)});
  geometry.AddTimestamps({0, 1, 2});
  geometry.AddLine(
      {PointWithAltitude({2.0, 2.0}, 50), PointWithAltitude({3.0, 3.0}, 75), PointWithAltitude({3.0, 3.0}, 60)});
  geometry.AddTimestamps({0, 0, 0});
  geometry.AddLine({PointWithAltitude({4.0, 4.0}, 200), PointWithAltitude({5.0, 5.0}, 250)});
  geometry.AddTimestamps({4, 5});
  auto const ts = TrackStatistics(geometry);

  TEST_EQUAL(ts.m_minElevation, 50, ());
  TEST_EQUAL(ts.m_maxElevation, 250, ());
  TEST_EQUAL(ts.m_ascent, 125, ());  // Ascent from 100 -> 150, 50 -> 75, 200 -> 250
  TEST_EQUAL(ts.m_descent, 25, ());  // Descent from 150 -> 140, 75 -> 60
  TEST_EQUAL(ts.m_duration, 3, ());
}

UNIT_TEST(TrackStatistics_WithGpsPoints)
{
  std::vector<std::vector<GpsInfo>> const pointsData = {
      {BuildGpsInfo(0.0, 0.0, 0, 0), BuildGpsInfo(1.0, 1.0, 50, 1), BuildGpsInfo(2.0, 2.0, 100, 2)},
      {BuildGpsInfo(3.0, 3.0, -50, 5)},
      {BuildGpsInfo(4.0, 4.0, 0, 10)}};
  TrackStatistics ts;
  for (auto const & pointsList : pointsData)
    for (auto const & point : pointsList)
      ts.AddGpsInfoPoint(point);
  TEST_EQUAL(ts.m_minElevation, -50, ());
  TEST_EQUAL(ts.m_maxElevation, 100, ());
  TEST_EQUAL(ts.m_ascent, 150, ());   // Ascent from 0 -> 50, 50 -> 100, -50 -> 0
  TEST_EQUAL(ts.m_descent, 150, ());  // Descent from 100 -> -50
  TEST_EQUAL(ts.m_duration, 10, ());
}

UNIT_TEST(TrackStatistics_PositiveAndNegativeAltitudes)
{
  kml::MultiGeometry geometry;
  geometry.AddLine({PointWithAltitude({0.0, 0.0}, -10), PointWithAltitude({1.0, 1.0}, 20),
                    PointWithAltitude({2.0, 2.0}, -5), PointWithAltitude({3.0, 3.0}, 15)});
  auto const ts = TrackStatistics(geometry);

  TEST_EQUAL(ts.m_minElevation, -10, ());
  TEST_EQUAL(ts.m_maxElevation, 20, ());
  TEST_EQUAL(ts.m_ascent, 50, ());   // Ascent from -10 -> 20 and -5 -> 15
  TEST_EQUAL(ts.m_descent, 25, ());  // Descent from 20 -> -5
}

UNIT_TEST(TrackStatistics_SmallAltitudeDelta)
{
  // Промени под kElevationThresholdMeters (8 м) се игнорират — GPS шум.
  std::vector<GpsInfo> const points = {BuildGpsInfo(0.0, 0.0, 0),   BuildGpsInfo(1.0, 1.0, 0.2),
                                       BuildGpsInfo(2.0, 2.0, 0.4), BuildGpsInfo(3.0, 3.0, 0.6),
                                       BuildGpsInfo(4.0, 4.0, 0.8), BuildGpsInfo(5.0, 5.0, 1.0)};

  TrackStatistics ts;
  for (auto const & point : points)
    ts.AddGpsInfoPoint(point);

  TEST_EQUAL(ts.m_minElevation, 0, ());
  TEST_EQUAL(ts.m_maxElevation, 1, ());
  TEST_EQUAL(ts.m_ascent, 0, ());
  TEST_EQUAL(ts.m_descent, 0, ());
}

UNIT_TEST(TrackStatistics_ElevationNoiseFilter)
{
  // Симулация на GPS шум върху плосък терен: осцилации ±5 м около 500 м.
  // Без филтър: фиктивно изкачване ~30 м. С филтър (8 м праг): 0 м.
  std::vector<GpsInfo> const points = {
      BuildGpsInfo(0.0, 0.0, 500), BuildGpsInfo(1.0, 0.0, 505), BuildGpsInfo(2.0, 0.0, 498),
      BuildGpsInfo(3.0, 0.0, 503), BuildGpsInfo(4.0, 0.0, 497), BuildGpsInfo(5.0, 0.0, 504),
      BuildGpsInfo(6.0, 0.0, 499), BuildGpsInfo(7.0, 0.0, 502), BuildGpsInfo(8.0, 0.0, 500)};

  TrackStatistics ts;
  for (auto const & point : points)
    ts.AddGpsInfoPoint(point);

  TEST_EQUAL(ts.m_ascent, 0, ());
  TEST_EQUAL(ts.m_descent, 0, ());
}

UNIT_TEST(TrackStatistics_RealClimbAboveThreshold)
{
  // Реално изкачване: 500 м → 520 м → 510 м (20 м нагоре, 10 м надолу).
  // Всички промени надвишават прага от 8 м.
  std::vector<GpsInfo> const points = {BuildGpsInfo(0.0, 0.0, 500), BuildGpsInfo(1.0, 0.0, 520),
                                       BuildGpsInfo(2.0, 0.0, 510)};

  TrackStatistics ts;
  for (auto const & point : points)
    ts.AddGpsInfoPoint(point);

  TEST_EQUAL(ts.m_ascent, 20, ());
  TEST_EQUAL(ts.m_descent, 10, ());
}

UNIT_TEST(TrackStatistics_MixedMultiGeometryAndGpsPoints)
{
  kml::MultiGeometry geometry;
  auto const point1 = PointWithAltitude({0.0, 0.0}, 100);
  auto const point2 = PointWithAltitude({1.0, 1.0}, 150);
  auto const point3 = PointWithAltitude({2.0, 2.0}, 50);
  geometry.AddLine({point1, point2, point3});
  geometry.AddTimestamps({5, 6, 7});

  auto ts = TrackStatistics(geometry);

  std::vector<GpsInfo> const points = {BuildGpsInfo(3.0, 3.0, 60, 8), BuildGpsInfo(4.0, 4.0, 160, 10),
                                       BuildGpsInfo(4.0, 4.0, 20, 15)};

  for (auto const & point : points)
    ts.AddGpsInfoPoint(point);

  TEST_EQUAL(ts.m_minElevation, 20, ());
  TEST_EQUAL(ts.m_maxElevation, 160, ());
  TEST_EQUAL(ts.m_ascent, 160, ());   // 50 + 10 + 100
  TEST_EQUAL(ts.m_descent, 240, ());  // 100 + 140
  TEST_EQUAL(ts.m_duration, 10, ());  // 10
}
}  // namespace track_statistics_tests
