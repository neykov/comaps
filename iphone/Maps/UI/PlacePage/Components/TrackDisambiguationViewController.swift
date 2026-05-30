import UIKit

/// A bottom-sheet list shown when a single tap could select several objects - typically multiple
/// overlapping recorded tracks, or a track running close to a POI. Lets the user pick exactly one.
/// Scales to many tracks via a scrollable list and is presented as a resizable sheet.
final class TrackDisambiguationViewController: UITableViewController {

  private enum Row {
    case poi(title: String)
    case track(Track)
  }

  private let rows: [Row]
  private let onSelectTrack: (MWMTrackID) -> Void
  private let onSelectPOI: () -> Void
  private let onCancel: () -> Void

  /// - Parameters:
  ///   - trackIds: ids of the tracks under the tap, already sorted nearest-first.
  ///   - poiTitle: title of the POI/bookmark under the tap, or nil when the tap did not hit one.
  @objc
  init(trackIds: [NSNumber],
       poiTitle: String?,
       onSelectTrack: @escaping (MWMTrackID) -> Void,
       onSelectPOI: @escaping () -> Void,
       onCancel: @escaping () -> Void) {
    var rows: [Row] = []
    if let poiTitle, !poiTitle.isEmpty {
      rows.append(.poi(title: poiTitle))
    }
    let manager = BookmarksManager.shared()
    for number in trackIds {
      let trackId = number.uint64Value
      if manager.hasTrack(trackId) {
        rows.append(.track(manager.track(withId: trackId)))
      }
    }
    self.rows = rows
    self.onSelectTrack = onSelectTrack
    self.onSelectPOI = onSelectPOI
    self.onCancel = onCancel
    super.init(style: .plain)
  }

  required init?(coder: NSCoder) {
    fatalError("init(coder:) has not been implemented")
  }

  /// Wraps the chooser in a navigation controller configured as a resizable bottom sheet, ready to present.
  @objc
  func makePresentableController() -> UIViewController {
    let navigationController = UINavigationController(rootViewController: self)
    if let sheet = navigationController.sheetPresentationController {
      sheet.detents = [.medium(), .large()]
      sheet.prefersGrabberVisible = true
      sheet.prefersScrollingExpandsWhenScrolledToEdge = false
    }
    return navigationController
  }

  override func viewDidLoad() {
    super.viewDidLoad()
    title = L("tracks_title")
    navigationItem.rightBarButtonItem = UIBarButtonItem(barButtonSystemItem: .cancel,
                                                        target: self,
                                                        action: #selector(cancelTapped))
    tableView.register(UITableViewCell.self, forCellReuseIdentifier: "cell")
    tableView.rowHeight = UITableView.automaticDimension
    tableView.estimatedRowHeight = 56
  }

  @objc private func cancelTapped() {
    dismiss(animated: true) { [onCancel] in onCancel() }
  }

  override func tableView(_ tableView: UITableView, numberOfRowsInSection section: Int) -> Int {
    return rows.count
  }

  override func tableView(_ tableView: UITableView, cellForRowAt indexPath: IndexPath) -> UITableViewCell {
    let cell = tableView.dequeueReusableCell(withIdentifier: "cell", for: indexPath)
    var content = UIListContentConfiguration.subtitleCell()
    switch rows[indexPath.row] {
    case .poi(let title):
      content.text = title
      content.image = UIImage(systemName: "mappin.circle.fill")
    case .track(let track):
      content.text = track.trackName
      content.secondaryText = "\(L("length")) \(DistanceFormatter.distanceString(fromMeters: Double(track.trackLengthMeters)))"
      content.image = circleImageForColor(track.trackColor, frameSize: 22)
    }
    cell.contentConfiguration = content
    cell.accessoryType = .disclosureIndicator
    return cell
  }

  override func tableView(_ tableView: UITableView, didSelectRowAt indexPath: IndexPath) {
    tableView.deselectRow(at: indexPath, animated: true)
    let row = rows[indexPath.row]
    dismiss(animated: true) { [onSelectTrack, onSelectPOI] in
      switch row {
      case .poi:
        onSelectPOI()
      case .track(let track):
        onSelectTrack(track.trackId)
      }
    }
  }
}
