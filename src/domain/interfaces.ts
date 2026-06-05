export interface Transaction {
  data: string;
  valor_bruto: number;
  valor_liquido: number;
  valor_repasse: number;
  valor_taxa: number;
  valor: number;
  valor_formatado: string;
  valor_bruto_formatado: string;
  valor_liquido_formatado: string;
  valor_repasse_formatado: string;
  valor_taxa_formatado: string;
  tipo: 'Crédito' | 'Estorno';
}

export interface DiscardedRecord {
  linha: number;
  conteudo: Record<string, string>;
}

export interface ReconciliationSummary {
  arquivo: string;
  periodo: string;
  total_registros: number;
  no_periodo: number;
  creditos_qtd: number;
  creditos_valor: number;
  creditos_formatado: string;
  estornos_qtd: number;
  estornos_valor: number;
  estornos_formatado: string;
  descartados: number;
  valor_bruto_total: number;
  valor_liquido_total: number;
  valor_repasse_total: number;
  valor_taxa_total: number;
  volume_total: number;
  volume_total_formatado: string;
  volume_bruto_formatado: string;
  volume_liquido_formatado: string;
  volume_repasse_formatado: string;
  volume_taxa_formatado: string;
}

export interface ChartData {
  labels: string[];
  valores: number[];
}

export interface ReconciliationResponse {
  status: 'success' | 'DISCREPANCIA_FINANCEIRA' | 'ERRO_LEITURA_ARQUIVO';
  motivo?: string;
  message?: string;
  delegacao_trace?: any;
  resumo?: ReconciliationSummary;
  transacoes?: Transaction[];
  chart_data?: ChartData;
  descartados_detalhes?: DiscardedRecord[];
}

export interface LocalFile {
  nome: string;
  caminho: string;
  tamanho: number;
  pasta_origem: string;
}

export interface AnalyzeResponse {
  status: 'success' | 'error';
  min_date?: string;
  max_date?: string;
  min_date_formatted?: string;
  max_date_formatted?: string;
  total_registros?: number;
  message?: string;
}
