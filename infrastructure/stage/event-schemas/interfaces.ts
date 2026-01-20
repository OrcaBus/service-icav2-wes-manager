export type SchemaNames = 'icav2WesAnalysisStateChange' | 'icav2WesRequest';

export const schemaNamesList: SchemaNames[] = ['icav2WesAnalysisStateChange', 'icav2WesRequest'];

export interface BuildSchemaProps {
  schemaName: SchemaNames;
}
