# 管理站点，模型
from django.db import models


class Site(models.Model):
    """
    站点模型，存储需要爬取和索引的站点信息
    """
    id = models.CharField(max_length=100, primary_key=True, help_text="站点唯一标识符")
    name = models.CharField(max_length=255, help_text="站点名称")
    description = models.TextField(null=True, blank=True, help_text="站点描述")
    base_url = models.URLField(max_length=2048, help_text="站点基础URL")
    icon = models.URLField(max_length=2048, null=True, blank=True, help_text="站点图标URL")
    enabled = models.BooleanField(default=True, help_text="是否启用")
    created_at = models.DateTimeField(auto_now_add=True, help_text="创建时间")
    updated_at = models.DateTimeField(auto_now=True, help_text="更新时间")
    last_crawl_time = models.DateTimeField(null=True, blank=True, help_text="最后爬取时间")
    total_documents = models.IntegerField(default=0, help_text="总文档数")
    metadata = models.JSONField(default=dict, help_text="站点元数据")

    class Meta:
        db_table = 'sitesearch_site'
        ordering = ['name']

    def __str__(self):
        return f"{self.name} ({self.id})"


class CrawlPolicy(models.Model):
    """
    爬取策略模型，定义站点的爬取规则和配置
    """
    site = models.ForeignKey(Site, on_delete=models.CASCADE, related_name='crawl_policies', help_text="关联站点")
    name = models.CharField(max_length=255, help_text="策略名称")
    description = models.TextField(null=True, blank=True, help_text="策略描述")
    start_urls = models.JSONField(default=list, help_text="起始URL列表")
    url_patterns = models.JSONField(default=list, help_text="URL正则匹配规则列表")
    exclude_patterns = models.JSONField(default=list, help_text="排除的URL规则列表")
    max_depth = models.IntegerField(default=3, help_text="最大爬取深度")
    max_urls = models.IntegerField(default=1000, help_text="最大爬取URL数量")
    crawl_delay = models.FloatField(default=0.5, help_text="爬取延迟时间(秒)")
    follow_robots_txt = models.BooleanField(default=True, help_text="是否遵循robots.txt规则")
    discover_sitemap = models.BooleanField(default=True, help_text="是否自动发现sitemap")
    respect_meta_robots = models.BooleanField(default=True, help_text="是否遵循meta robots规则")
    allow_subdomains = models.BooleanField(default=False, help_text="是否允许爬取子域名")
    allow_external_links = models.BooleanField(default=False, help_text="是否允许爬取外部链接")
    allowed_content_types = models.JSONField(default=list, help_text="允许的内容类型列表")
    created_at = models.DateTimeField(auto_now_add=True, help_text="创建时间")
    updated_at = models.DateTimeField(auto_now=True, help_text="更新时间")
    last_executed = models.DateTimeField(null=True, blank=True, help_text="最后执行时间")
    enabled = models.BooleanField(default=True, help_text="是否启用")
    crawler_type = models.CharField(max_length=50, default="firecrawl", help_text="爬虫类型")
    advanced_config = models.JSONField(default=dict, help_text="高级配置选项")

    class Meta:
        db_table = 'sitesearch_crawl_policy'
        ordering = ['-updated_at']
        unique_together = [['site', 'name']]

    def __str__(self):
        return f"{self.name} ({self.site.name})"


class ScheduleTask(models.Model):
    """
    定时任务模型，配置爬取策略的定时执行计划
    """
    SCHEDULE_TYPES = [
        ('once', '单次执行'),
        ('interval', '间隔执行'),
        ('cron', 'Cron表达式')
    ]

    crawl_policy = models.ForeignKey(CrawlPolicy, on_delete=models.CASCADE, related_name='schedules', help_text="关联的爬取策略")
    name = models.CharField(max_length=255, help_text="任务名称")
    description = models.TextField(null=True, blank=True, help_text="任务描述")
    schedule_type = models.CharField(max_length=20, choices=SCHEDULE_TYPES, help_text="调度类型")
    cron_expression = models.CharField(max_length=100, null=True, blank=True, help_text="Cron表达式")
    interval_seconds = models.IntegerField(null=True, blank=True, help_text="间隔时间(秒)")
    one_time_date = models.DateTimeField(null=True, blank=True, help_text="单次执行时间")
    start_date = models.DateTimeField(null=True, blank=True, help_text="开始日期")
    end_date = models.DateTimeField(null=True, blank=True, help_text="结束日期")
    created_at = models.DateTimeField(auto_now_add=True, help_text="创建时间")
    updated_at = models.DateTimeField(auto_now=True, help_text="更新时间")
    last_run = models.DateTimeField(null=True, blank=True, help_text="上次运行时间")
    next_run = models.DateTimeField(null=True, blank=True, help_text="下次运行时间")
    enabled = models.BooleanField(default=True, help_text="是否启用")
    job_id = models.CharField(max_length=255, null=True, blank=True, help_text="任务调度器中的作业ID")
    run_count = models.IntegerField(default=0, help_text="运行次数")
    max_runs = models.IntegerField(null=True, blank=True, help_text="最大运行次数")
    metadata = models.JSONField(default=dict, help_text="元数据")

    class Meta:
        db_table = 'sitesearch_schedule_task'
        ordering = ['-updated_at']

    def __str__(self):
        return f"{self.name} ({self.crawl_policy.name})"


class RefreshPolicy(models.Model):
    """
    刷新策略模型，定义站点内容的刷新规则
    """
    REFRESH_STRATEGIES = [
        ('all', '全量刷新'),
        ('incremental', '增量刷新'),
        ('selective', '选择性刷新')
    ]

    site = models.OneToOneField(Site, on_delete=models.CASCADE, related_name='refresh_policy', help_text="关联站点")
    strategy = models.CharField(max_length=20, choices=REFRESH_STRATEGIES, default='incremental', help_text="刷新策略")
    name = models.CharField(max_length=255, default="Default Refresh Policy", help_text="策略名称")
    description = models.TextField(null=True, blank=True, help_text="策略描述")
    refresh_interval_days = models.IntegerField(default=7, help_text="刷新间隔(天)")
    url_patterns = models.JSONField(default=list, help_text="要刷新的URL模式列表")
    exclude_patterns = models.JSONField(default=list, help_text="排除刷新的URL模式列表")
    max_age_days = models.IntegerField(default=30, help_text="内容最大有效期(天)")
    priority_patterns = models.JSONField(default=list, help_text="优先刷新的URL模式列表")
    created_at = models.DateTimeField(auto_now_add=True, help_text="创建时间")
    updated_at = models.DateTimeField(auto_now=True, help_text="更新时间")
    last_refresh = models.DateTimeField(null=True, blank=True, help_text="上次刷新时间")
    next_refresh = models.DateTimeField(null=True, blank=True, help_text="下次刷新时间")
    enabled = models.BooleanField(default=True, help_text="是否启用")
    advanced_config = models.JSONField(default=dict, help_text="高级配置选项")

    class Meta:
        db_table = 'sitesearch_refresh_policy'
        ordering = ['-updated_at']

    def __str__(self):
        return f"{self.name} ({self.site.name})"


class SystemSettings(models.Model):
    """
    系统设置模型，存储全局系统配置参数
    """
    key = models.CharField(max_length=255, primary_key=True, help_text="设置键名")
    value = models.JSONField(help_text="设置值")
    description = models.TextField(null=True, blank=True, help_text="设置描述")
    created_at = models.DateTimeField(auto_now_add=True, help_text="创建时间")
    updated_at = models.DateTimeField(auto_now=True, help_text="更新时间")
    category = models.CharField(max_length=100, db_index=True, help_text="设置类别")
    is_secret = models.BooleanField(default=False, help_text="是否为敏感信息")

    class Meta:
        db_table = 'sitesearch_system_settings'
        ordering = ['category', 'key']

    def __str__(self):
        return f"{self.key} ({self.category})"


class SearchLog(models.Model):
    """
    搜索日志模型，记录用户搜索行为和结果
    """
    query = models.CharField(max_length=1024, help_text="搜索查询")
    search_type = models.CharField(max_length=50, help_text="搜索类型(全文/语义)")
    site_id = models.CharField(max_length=100, null=True, blank=True, help_text="站点ID(如果针对特定站点)")
    timestamp = models.DateTimeField(auto_now_add=True, help_text="搜索时间")
    results_count = models.IntegerField(default=0, help_text="结果数量")
    execution_time_ms = models.IntegerField(help_text="执行时间(毫秒)")
    user_ip = models.GenericIPAddressField(null=True, blank=True, help_text="用户IP")
    user_agent = models.TextField(null=True, blank=True, help_text="用户代理")
    filters = models.JSONField(default=dict, help_text="搜索过滤器")
    user_feedback = models.IntegerField(null=True, blank=True, help_text="用户反馈(-1:不满意,0:中立,1:满意)")
    result_ids = models.JSONField(default=list, help_text="返回的结果ID列表")
    metadata = models.JSONField(default=dict, help_text="元数据")

    class Meta:
        db_table = 'sitesearch_search_log'
        indexes = [
            models.Index(fields=['query']),
            models.Index(fields=['search_type']),
            models.Index(fields=['site_id']),
            models.Index(fields=['timestamp']),
        ]
        ordering = ['-timestamp']

    def __str__(self):
        return f"{self.query[:50]} ({self.search_type})"

