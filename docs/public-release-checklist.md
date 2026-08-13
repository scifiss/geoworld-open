# Public Release Checklist

This checklist separates repository checks from the final GitHub actions needed
before GeoWorld Open becomes public. It does not authorize a visibility change,
tag, package publication, or merge by itself.

## Completed automatically

- [x] Compile public source, applications, scripts, and tests.
- [x] Run the complete deterministic test suite.
- [x] Run the tracked-file secret scanner locally.
- [x] Build and inspect the wheel and complete public source distribution.
- [x] Verify a fresh environment can install and run the flagship workflow.
- [x] Exercise structural World, layered-reservoir, and CO2 examples.
- [x] Check local README and architecture-document links.
- [x] Confirm Apache-2.0 metadata, LICENSE, and NOTICE are packaged.

## Final manual review

- [ ] Review the complete branch diff and tracked-file inventory.
- [ ] Confirm all scenarios, fixtures, figures, and documentation are intended for
      public distribution and have no private or third-party attribution issue.
- [ ] Confirm commit-author names and email addresses are intended to become public.
- [ ] Confirm the private GeoWorld repository remains private and separate.
- [ ] Confirm required CI, tracked-file Secret Scan, and full-history Gitleaks
      workflows are green on the release commit.

## GitHub UI actions

- [ ] Set the repository description and focused topics approved for release.
- [ ] Block force pushes and branch deletion on `main`.
- [ ] Require passing CI before merge; require pull requests when collaboration begins.
- [ ] Reconfirm the default branch and Apache-2.0 license display.
- [ ] Change repository visibility only after every prior item is complete.

## Deferred release actions

- [ ] Merge the approved release branch into `main`.
- [ ] Create a version tag or GitHub release only after the public-release gate closes.
- [ ] Publish a package only through a separately reviewed packaging release process.
