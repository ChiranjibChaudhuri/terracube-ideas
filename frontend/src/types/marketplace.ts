export type ServiceType = 'DATA_SOURCE' | 'ANALYTIC';

export interface Service {
    id: string;
    name: string;
    type: ServiceType;
    description: string;
    input_schema: any;
    tags: string[];
}
