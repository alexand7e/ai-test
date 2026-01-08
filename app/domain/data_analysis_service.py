import pandas as pd
import json
from pathlib import Path
from typing import List, Dict, Any, Optional
import logging
import os

logger = logging.getLogger(__name__)


class DataAnalysisService:
    """Serviço de análise de dados usando pandas"""
    
    def __init__(self, data_dir: str = "./data"):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self._dataframes: Dict[str, Dict[str, pd.DataFrame]] = {}  # agent_id -> {filename: DataFrame}
    
    def _get_agent_data_dir(self, agent_id: str) -> Path:
        """Retorna o diretório de dados de um agente"""
        agent_dir = self.data_dir / "agents" / agent_id / "files"
        agent_dir.mkdir(parents=True, exist_ok=True)
        return agent_dir
    
    def _load_file(self, file_path: Path) -> Optional[pd.DataFrame]:
        """Carrega um arquivo em DataFrame"""
        try:
            suffix = file_path.suffix.lower()
            
            if suffix == '.csv':
                return pd.read_csv(file_path)
            elif suffix == '.json':
                # Tenta carregar como JSON array ou JSON lines
                with open(file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    if isinstance(data, list):
                        return pd.DataFrame(data)
                    elif isinstance(data, dict):
                        # Se for um objeto único, tenta normalizar
                        return pd.json_normalize(data)
                    else:
                        return pd.DataFrame([data])
            elif suffix in ['.xlsx', '.xls']:
                return pd.read_excel(file_path)
            else:
                logger.warning(f"Unsupported file type: {suffix}")
                return None
                
        except Exception as e:
            logger.error(f"Error loading file {file_path}: {e}", exc_info=True)
            return None
    
    def save_file(self, agent_id: str, filename: str, file_content: bytes) -> bool:
        """Salva um arquivo para um agente"""
        try:
            agent_dir = self._get_agent_data_dir(agent_id)
            file_path = agent_dir / filename
            
            # Validação de segurança: apenas permite extensões específicas
            allowed_extensions = {'.csv', '.json', '.xlsx', '.xls'}
            if file_path.suffix.lower() not in allowed_extensions:
                logger.error(f"File type not allowed: {file_path.suffix}")
                return False
            
            # Salva arquivo
            with open(file_path, 'wb') as f:
                f.write(file_content)
            
            # Carrega DataFrame
            df = self._load_file(file_path)
            if df is not None:
                if agent_id not in self._dataframes:
                    self._dataframes[agent_id] = {}
                self._dataframes[agent_id][filename] = df
                logger.info(f"Saved and loaded file {filename} for agent {agent_id}")
                return True
            else:
                logger.error(f"Failed to load DataFrame from {filename}")
                return False
                
        except Exception as e:
            logger.error(f"Error saving file: {e}", exc_info=True)
            return False
    
    def list_files(self, agent_id: str) -> List[Dict[str, Any]]:
        """Lista arquivos de um agente"""
        try:
            agent_dir = self._get_agent_data_dir(agent_id)
            files = []
            
            for file_path in agent_dir.iterdir():
                if file_path.is_file():
                    file_info = {
                        "filename": file_path.name,
                        "size": file_path.stat().st_size,
                        "extension": file_path.suffix
                    }
                    
                    # Adiciona informações do DataFrame se carregado
                    if agent_id in self._dataframes and file_path.name in self._dataframes[agent_id]:
                        df = self._dataframes[agent_id][file_path.name]
                        file_info["rows"] = len(df)
                        file_info["columns"] = list(df.columns)
                    
                    files.append(file_info)
            
            return files
            
        except Exception as e:
            logger.error(f"Error listing files: {e}", exc_info=True)
            return []
    
    def delete_file(self, agent_id: str, filename: str) -> bool:
        """Remove um arquivo de um agente"""
        try:
            agent_dir = self._get_agent_data_dir(agent_id)
            file_path = agent_dir / filename
            
            if not file_path.exists():
                logger.warning(f"File not found: {file_path}")
                return False
            
            # Remove arquivo
            file_path.unlink()
            
            # Remove do cache de DataFrames
            if agent_id in self._dataframes:
                self._dataframes[agent_id].pop(filename, None)
            
            logger.info(f"Deleted file {filename} for agent {agent_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error deleting file: {e}", exc_info=True)
            return False
    
    def load_agent_files(self, agent_id: str, filenames: List[str]) -> bool:
        """Carrega arquivos de um agente na memória"""
        try:
            agent_dir = self._get_agent_data_dir(agent_id)
            
            if agent_id not in self._dataframes:
                self._dataframes[agent_id] = {}
            
            for filename in filenames:
                file_path = agent_dir / filename
                if file_path.exists():
                    df = self._load_file(file_path)
                    if df is not None:
                        self._dataframes[agent_id][filename] = df
                        logger.info(f"Loaded file {filename} for agent {agent_id}")
                else:
                    logger.warning(f"File not found: {file_path}")
            
            return True
            
        except Exception as e:
            logger.error(f"Error loading agent files: {e}", exc_info=True)
            return False
    
    def execute_query(self, agent_id: str, query: str) -> Dict[str, Any]:
        """Executa uma query pandas nos dados do agente"""
        try:
            if agent_id not in self._dataframes or not self._dataframes[agent_id]:
                return {
                    "success": False,
                    "error": "No data files loaded for this agent"
                }
            
            # Combina todos os DataFrames do agente em um único DataFrame
            # Usa o primeiro arquivo como base ou combina todos
            dfs = list(self._dataframes[agent_id].values())
            if not dfs:
                return {
                    "success": False,
                    "error": "No data available"
                }
            
            # Se houver múltiplos DataFrames, combina ou usa o primeiro
            if len(dfs) == 1:
                df = dfs[0]
            else:
                # Combina todos os DataFrames (concatena)
                df = pd.concat(dfs, ignore_index=True)
            
            # Executa query de forma segura
            try:
                # Sanitiza query básica (remove comandos perigosos)
                forbidden_keywords = ['import', 'exec', 'eval', '__', 'open', 'file', 'system', 'os', 'subprocess', 'globals', 'locals']
                query_lower = query.lower()
                if any(keyword in query_lower for keyword in forbidden_keywords):
                    return {
                        "success": False,
                        "error": "Query contains forbidden operations"
                    }
                
                # Tenta executar como query string primeiro
                if query.strip().startswith('df.'):
                    # Remove 'df.' do início
                    query = query.strip()[3:].strip()
                
                # Executa query de forma segura
                try:
                    # Tenta como query string do pandas
                    if 'query(' in query_lower or query_lower.startswith('query'):
                        # Extrai a condição do query()
                        if '(' in query and ')' in query:
                            condition = query[query.find('(')+1:query.rfind(')')].strip()
                            if condition.startswith('"') or condition.startswith("'"):
                                condition = condition[1:-1]
                            result = df.query(condition)
                        else:
                            result = df
                    else:
                        # Tenta métodos comuns do pandas de forma segura
                        if query_lower.startswith('head'):
                            n = 10
                            if '(' in query and ')' in query:
                                try:
                                    n = int(query[query.find('(')+1:query.rfind(')')])
                                except:
                                    pass
                            result = df.head(n)
                        elif query_lower.startswith('tail'):
                            n = 10
                            if '(' in query and ')' in query:
                                try:
                                    n = int(query[query.find('(')+1:query.rfind(')')])
                                except:
                                    pass
                            result = df.tail(n)
                        elif query_lower.startswith('describe'):
                            result = df.describe()
                        elif query_lower.startswith('info'):
                            result = pd.DataFrame({'info': [str(df.info())]})
                        elif query_lower.startswith('columns'):
                            result = pd.DataFrame({'columns': df.columns.tolist()})
                        elif query_lower.startswith('shape'):
                            result = pd.DataFrame({'shape': [f"{df.shape[0]} rows, {df.shape[1]} columns"]})
                        elif '[' in query and ']' in query:
                            # Tenta indexação segura
                            # Exemplo: df['coluna'] ou df[df['coluna'] > 10]
                            # Por segurança, apenas permite operações básicas
                            result = df
                        else:
                            # Fallback: retorna informações básicas
                            result = df.head(10)
                except Exception as query_error:
                    return {
                        "success": False,
                        "error": f"Query execution error: {str(query_error)}. Tente usar métodos como: head(), tail(), describe(), ou filtros como df[df['coluna'] > valor]"
                    }
                
                # Converte resultado para formato serializável
                if isinstance(result, pd.DataFrame):
                    return {
                        "success": True,
                        "result": result.to_dict(orient='records'),
                        "rows": len(result),
                        "columns": list(result.columns)
                    }
                elif isinstance(result, pd.Series):
                    return {
                        "success": True,
                        "result": result.to_dict(),
                        "type": "series"
                    }
                else:
                    return {
                        "success": True,
                        "result": str(result),
                        "type": "scalar"
                    }
                    
            except Exception as e:
                return {
                    "success": False,
                    "error": f"Query execution error: {str(e)}"
                }
                
        except Exception as e:
            logger.error(f"Error executing query: {e}", exc_info=True)
            return {
                "success": False,
                "error": str(e)
            }
    
    def get_dataframe_info(self, agent_id: str) -> Dict[str, Any]:
        """Retorna informações sobre os DataFrames carregados"""
        if agent_id not in self._dataframes or not self._dataframes[agent_id]:
            return {"files": []}
        
        info = {"files": []}
        for filename, df in self._dataframes[agent_id].items():
            info["files"].append({
                "filename": filename,
                "rows": len(df),
                "columns": list(df.columns),
                "dtypes": df.dtypes.astype(str).to_dict(),
                "sample": df.head(5).to_dict(orient='records') if len(df) > 0 else []
            })
        
        return info

