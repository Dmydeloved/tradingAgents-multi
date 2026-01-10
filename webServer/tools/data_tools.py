import akshare as ak
import pandas as pd
from typing import List, Dict, Any

class StockIndustryMacroFetcher:

    # ----------------------------
    # 行业数据部分
    # ----------------------------
    @staticmethod
    def get_industry_info(stock_codes: List[str]) -> Dict[str, Dict[str, Any]]:
        """
        获取行业分类、概念分类
        采用申万（SW）行业数据 + 概念股数据
        """
        result = {}

        # 申万行业分类（包含全部股票）
        sw_df = ak.sw_index_cons_spot()  # 申万行业成分股
        sw_df = sw_df.rename(columns={"股票代码": "code"})

        # 概念股（如有需要可按多个接口）
        concept_df = ak.stock_board_concept_cons_em()

        for code in stock_codes:
            code_clean = code.replace(".SZ", "").replace(".SH", "")

            # 行业
            industry_row = sw_df[sw_df["code"] == code_clean]
            if not industry_row.empty:
                industry_name = industry_row.iloc[0]["板块名称"]
                industry_code = industry_row.iloc[0]["板块代码"]
            else:
                industry_name, industry_code = None, None

            # 概念
            concepts = concept_df[concept_df["代码"] == code_clean]["板块名称"].tolist()

            result[code] = {
                "industry": industry_name,
                "industry_code": industry_code,
                "concepts": concepts,
            }

        return result

    # ----------------------------
    # 宏观数据部分
    # ----------------------------
    @staticmethod
    def get_macro_data() -> Dict[str, pd.DataFrame]:
        """
        获取常用宏观数据：
        - 中国GDP（季度）
        - PMI（制造业）
        - CPI
        - 社会融资规模
        - 利率
        - 汇率（美元兑人民币）
        """
        macro_data = {}

        try:
            macro_data["gdp"] = ak.macro_china_gdp_quarterly()
        except:
            macro_data["gdp"] = None

        try:
            macro_data["pmi"] = ak.macro_china_pmi()
        except:
            macro_data["pmi"] = None

        try:
            macro_data["cpi"] = ak.macro_china_cpi_monthly()
        except:
            macro_data["cpi"] = None

        try:
            macro_data["tsf"] = ak.macro_china_tsr()   # 社会融资规模
        except:
            macro_data["tsf"] = None

        try:
            macro_data["loan_rate"] = ak.macro_china_lpr()  # 贷款市场报价利率
        except:
            macro_data["loan_rate"] = None

        try:
            macro_data["usd_cny"] = ak.fx_sina_usd()  # 人民币汇率
        except:
            macro_data["usd_cny"] = None

        return macro_data

    # ----------------------------
    # 总入口：行业 + 宏观
    # ----------------------------
    @staticmethod
    def fetch(stock_codes: List[str]) -> Dict[str, Any]:
        return {
            "industry": StockIndustryMacroFetcher.get_industry_info(stock_codes),
            "macro": StockIndustryMacroFetcher.get_macro_data()
        }

# ====================== 测试代码（直接运行）======================
if __name__ == "__main__":
    print("="*60)
    print("开始测试 StockDataTools 所有核心函数（兼容旧AKShare）")
    print("="*60 + "\n")

    # ---------------------- 测试1：get_stock_industry ----------------------
    print("【测试1】get_stock_industry（获取股票所属行业）")
    test_stocks = [
        "600519.SH",  # 贵州茅台（A股沪市）
        "000858.SZ",  # 五粮液（A股深市）
        "00700.HK",   # 腾讯控股（港股）
        "123456.XY",  # 无效市场代码
        "6000000.SH"  # 无效A股代码
    ]
    industry_result = StockDataTools.get_stock_industry(test_stocks)
    for code, industry in industry_result.items():
        print(f"  {code} → {industry}")
    print("✅ 测试1完成（查看上述输出是否符合预期）\n")

    # ---------------------- 测试2：get_industry_data ----------------------
    print("【测试2】get_industry_data（获取行业核心数据）")
    test_industry_args = IndustryDataQueryArgs(
        industry_name="食品饮料",
        start_date="20240101",
        end_date=pd.Timestamp.now().strftime("%Y%m%d")
    )
    industry_data_result = StockDataTools.get_industry_data(test_industry_args)
    print(industry_data_result)
    print("✅ 测试2完成（查看上述行业数据是否完整）\n")

    # ---------------------- 测试3：get_macro_data ----------------------
    print("【测试3】get_macro_data（获取宏观经济数据）")
    test_macro_args = MacroDataQueryArgs(
        indicator=["GDP", "CPI", "PPI", "利率", "汇率"],
        start_date="20240101",
        end_date=pd.Timestamp.now().strftime("%Y%m%d")
    )
    macro_data_result = StockDataTools.get_macro_data(test_macro_args)
    print(macro_data_result)
    print("✅ 测试3完成（查看上述宏观数据是否完整）\n")

    print("="*60)
    print("所有测试执行完毕！")
    print("验证标准：")
    print("1. 测试1：有效A股/港股返回行业名称，无scalar values错误")
    print("2. 测试2：显示估值、财务、指数走势数据，无接口不存在错误")
    print("3. 测试3：显示GDP/CPI/PPI/利率/汇率数据，无字段名错误")
    print("="*60)