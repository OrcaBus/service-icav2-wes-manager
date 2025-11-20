export type SchemaNames = 'analysisStateChange' | 'wesRequest';

export const schemaNamesList: SchemaNames[] = ['analysisStateChange', 'wesRequest'];

export interface BuildSchemaProps {
  schemaName: SchemaNames;
}
