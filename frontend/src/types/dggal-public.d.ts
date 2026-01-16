declare module '/dggal/dggal.js' {
  export class DGGAL {
    static init: () => Promise<DGGAL>;
    static nullZone: bigint;
    createDGGRS: (name: string) => {
      getZoneFromTextID: (zoneId: string) => bigint;
      getZoneRefinedWGS84Vertices: (zone: bigint, edgeRefinement: number) => { lat: number; lon: number }[];
      getZoneTextID: (zone: bigint) => string;
      getZoneLevel: (zone: bigint) => number;
      listZones: (
        level: number,
        bbox: { ll: { lat: number; lon: number }; ur: { lat: number; lon: number } }
      ) => bigint[];
      getLevelFromPixelsAndExtent: (
        extent: { ll: { lat: number; lon: number }; ur: { lat: number; lon: number } },
        width: number,
        height: number,
        relativeDepth: number
      ) => number;
    };
  }

  export default DGGAL;
}
