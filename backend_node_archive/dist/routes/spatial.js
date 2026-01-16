import { z } from 'zod';
import { loadDggal } from '../dggal.js';
const spatialOpSchema = z.discriminatedUnion('type', [
    z.object({
        type: z.literal('neighbors'),
        dggid: z.string(),
    }),
    z.object({
        type: z.literal('parent'),
        dggid: z.string(),
    }),
    z.object({
        type: z.literal('children'),
        dggid: z.string(),
    }),
    z.object({
        type: z.literal('vertices'),
        dggid: z.string(),
    }),
]);
export const spatialRoutes = async (app) => {
    app.post('/api/ops/spatial', async (request, reply) => {
        // await request.jwtVerify(); // Optional: secure if needed
        const bodyResult = spatialOpSchema.safeParse(request.body);
        if (!bodyResult.success) {
            return reply.code(400).send({ error: bodyResult.error });
        }
        const op = bodyResult.data;
        const dggal = await loadDggal();
        const dggrs = dggal.createDGGRS('IVEA3H');
        try {
            const zone = dggrs.getZoneFromTextID(op.dggid);
            if (op.type === 'neighbors') {
                const neighbors = dggrs.getZoneNeighbors(zone);
                return {
                    dggid: op.dggid,
                    neighbors: neighbors.map((n) => ({
                        dggid: dggrs.getZoneTextID(n.zone),
                        type: n.type,
                    })),
                };
            }
            if (op.type === 'parent') {
                const parents = dggrs.getZoneParents(zone);
                // Usually interest is in the immediate parent (first in list or specific level)
                // ISEA3H parents list might contain multiple, but let's return all mappable
                return {
                    dggid: op.dggid,
                    parents: parents.map((p) => dggrs.getZoneTextID(p)),
                };
            }
            if (op.type === 'children') {
                const children = dggrs.getZoneChildren(zone);
                return {
                    dggid: op.dggid,
                    children: children.map((c) => dggrs.getZoneTextID(c)),
                };
            }
            if (op.type === 'vertices') {
                const vertices = dggrs.getZoneWGS84Vertices(zone);
                return {
                    dggid: op.dggid,
                    vertices,
                };
            }
        }
        finally {
            dggal.terminate();
        }
    });
};
