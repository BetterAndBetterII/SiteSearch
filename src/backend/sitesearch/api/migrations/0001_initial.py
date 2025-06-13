# Generated by Django 5.2 on 2025-04-24 06:47

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='CrawlPolicy',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(help_text='策略名称', max_length=255)),
                ('description', models.TextField(blank=True, help_text='策略描述', null=True)),
                ('start_urls', models.JSONField(default=list, help_text='起始URL列表')),
                ('url_patterns', models.JSONField(default=list, help_text='URL正则匹配规则列表')),
                ('exclude_patterns', models.JSONField(default=list, help_text='排除的URL规则列表')),
                ('max_depth', models.IntegerField(default=3, help_text='最大爬取深度')),
                ('max_urls', models.IntegerField(default=1000, help_text='最大爬取URL数量')),
                ('crawl_delay', models.FloatField(default=0.5, help_text='爬取延迟时间(秒)')),
                ('follow_robots_txt', models.BooleanField(default=True, help_text='是否遵循robots.txt规则')),
                ('discover_sitemap', models.BooleanField(default=True, help_text='是否自动发现sitemap')),
                ('respect_meta_robots', models.BooleanField(default=True, help_text='是否遵循meta robots规则')),
                ('allow_subdomains', models.BooleanField(default=False, help_text='是否允许爬取子域名')),
                ('allow_external_links', models.BooleanField(default=False, help_text='是否允许爬取外部链接')),
                ('allowed_content_types', models.JSONField(default=list, help_text='允许的内容类型列表')),
                ('created_at', models.DateTimeField(auto_now_add=True, help_text='创建时间')),
                ('updated_at', models.DateTimeField(auto_now=True, help_text='更新时间')),
                ('last_executed', models.DateTimeField(blank=True, help_text='最后执行时间', null=True)),
                ('enabled', models.BooleanField(default=True, help_text='是否启用')),
                ('crawler_type', models.CharField(default='firecrawl', help_text='爬虫类型', max_length=50)),
                ('advanced_config', models.JSONField(default=dict, help_text='高级配置选项')),
            ],
            options={
                'db_table': 'sitesearch_crawl_policy',
                'ordering': ['-updated_at'],
            },
        ),
        migrations.CreateModel(
            name='Site',
            fields=[
                ('id', models.CharField(help_text='站点唯一标识符', max_length=100, primary_key=True, serialize=False)),
                ('name', models.CharField(help_text='站点名称', max_length=255)),
                ('description', models.TextField(blank=True, help_text='站点描述', null=True)),
                ('base_url', models.URLField(help_text='站点基础URL', max_length=2048)),
                ('icon', models.URLField(blank=True, help_text='站点图标URL', max_length=2048, null=True)),
                ('enabled', models.BooleanField(default=True, help_text='是否启用')),
                ('created_at', models.DateTimeField(auto_now_add=True, help_text='创建时间')),
                ('updated_at', models.DateTimeField(auto_now=True, help_text='更新时间')),
                ('last_crawl_time', models.DateTimeField(blank=True, help_text='最后爬取时间', null=True)),
                ('total_documents', models.IntegerField(default=0, help_text='总文档数')),
                ('metadata', models.JSONField(default=dict, help_text='站点元数据')),
            ],
            options={
                'db_table': 'sitesearch_site',
                'ordering': ['name'],
            },
        ),
        migrations.CreateModel(
            name='SystemSettings',
            fields=[
                ('key', models.CharField(help_text='设置键名', max_length=255, primary_key=True, serialize=False)),
                ('value', models.JSONField(help_text='设置值')),
                ('description', models.TextField(blank=True, help_text='设置描述', null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True, help_text='创建时间')),
                ('updated_at', models.DateTimeField(auto_now=True, help_text='更新时间')),
                ('category', models.CharField(db_index=True, help_text='设置类别', max_length=100)),
                ('is_secret', models.BooleanField(default=False, help_text='是否为敏感信息')),
            ],
            options={
                'db_table': 'sitesearch_system_settings',
                'ordering': ['category', 'key'],
            },
        ),
        migrations.CreateModel(
            name='ScheduleTask',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(help_text='任务名称', max_length=255)),
                ('description', models.TextField(blank=True, help_text='任务描述', null=True)),
                ('schedule_type', models.CharField(choices=[('once', '单次执行'), ('interval', '间隔执行'), ('cron', 'Cron表达式')], help_text='调度类型', max_length=20)),
                ('cron_expression', models.CharField(blank=True, help_text='Cron表达式', max_length=100, null=True)),
                ('interval_seconds', models.IntegerField(blank=True, help_text='间隔时间(秒)', null=True)),
                ('one_time_date', models.DateTimeField(blank=True, help_text='单次执行时间', null=True)),
                ('start_date', models.DateTimeField(blank=True, help_text='开始日期', null=True)),
                ('end_date', models.DateTimeField(blank=True, help_text='结束日期', null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True, help_text='创建时间')),
                ('updated_at', models.DateTimeField(auto_now=True, help_text='更新时间')),
                ('last_run', models.DateTimeField(blank=True, help_text='上次运行时间', null=True)),
                ('next_run', models.DateTimeField(blank=True, help_text='下次运行时间', null=True)),
                ('enabled', models.BooleanField(default=True, help_text='是否启用')),
                ('job_id', models.CharField(blank=True, help_text='任务调度器中的作业ID', max_length=255, null=True)),
                ('run_count', models.IntegerField(default=0, help_text='运行次数')),
                ('max_runs', models.IntegerField(blank=True, help_text='最大运行次数', null=True)),
                ('metadata', models.JSONField(default=dict, help_text='元数据')),
                ('crawl_policy', models.ForeignKey(help_text='关联的爬取策略', on_delete=django.db.models.deletion.CASCADE, related_name='schedules', to='sitesearch_api.crawlpolicy')),
            ],
            options={
                'db_table': 'sitesearch_schedule_task',
                'ordering': ['-updated_at'],
            },
        ),
        migrations.CreateModel(
            name='SearchLog',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('query', models.CharField(help_text='搜索查询', max_length=1024)),
                ('search_type', models.CharField(help_text='搜索类型(全文/语义)', max_length=50)),
                ('site_id', models.CharField(blank=True, help_text='站点ID(如果针对特定站点)', max_length=100, null=True)),
                ('timestamp', models.DateTimeField(auto_now_add=True, help_text='搜索时间')),
                ('results_count', models.IntegerField(default=0, help_text='结果数量')),
                ('execution_time_ms', models.IntegerField(help_text='执行时间(毫秒)')),
                ('user_ip', models.GenericIPAddressField(blank=True, help_text='用户IP', null=True)),
                ('user_agent', models.TextField(blank=True, help_text='用户代理', null=True)),
                ('filters', models.JSONField(default=dict, help_text='搜索过滤器')),
                ('user_feedback', models.IntegerField(blank=True, help_text='用户反馈(-1:不满意,0:中立,1:满意)', null=True)),
                ('result_ids', models.JSONField(default=list, help_text='返回的结果ID列表')),
                ('metadata', models.JSONField(default=dict, help_text='元数据')),
            ],
            options={
                'db_table': 'sitesearch_search_log',
                'ordering': ['-timestamp'],
                'indexes': [models.Index(fields=['query'], name='sitesearch__query_e796ca_idx'), models.Index(fields=['search_type'], name='sitesearch__search__ad6490_idx'), models.Index(fields=['site_id'], name='sitesearch__site_id_c35e84_idx'), models.Index(fields=['timestamp'], name='sitesearch__timesta_e0b08e_idx')],
            },
        ),
        migrations.CreateModel(
            name='RefreshPolicy',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('strategy', models.CharField(choices=[('all', '全量刷新'), ('incremental', '增量刷新'), ('selective', '选择性刷新')], default='incremental', help_text='刷新策略', max_length=20)),
                ('name', models.CharField(default='Default Refresh Policy', help_text='策略名称', max_length=255)),
                ('description', models.TextField(blank=True, help_text='策略描述', null=True)),
                ('refresh_interval_days', models.IntegerField(default=7, help_text='刷新间隔(天)')),
                ('url_patterns', models.JSONField(default=list, help_text='要刷新的URL模式列表')),
                ('exclude_patterns', models.JSONField(default=list, help_text='排除刷新的URL模式列表')),
                ('max_age_days', models.IntegerField(default=30, help_text='内容最大有效期(天)')),
                ('priority_patterns', models.JSONField(default=list, help_text='优先刷新的URL模式列表')),
                ('created_at', models.DateTimeField(auto_now_add=True, help_text='创建时间')),
                ('updated_at', models.DateTimeField(auto_now=True, help_text='更新时间')),
                ('last_refresh', models.DateTimeField(blank=True, help_text='上次刷新时间', null=True)),
                ('next_refresh', models.DateTimeField(blank=True, help_text='下次刷新时间', null=True)),
                ('enabled', models.BooleanField(default=True, help_text='是否启用')),
                ('advanced_config', models.JSONField(default=dict, help_text='高级配置选项')),
                ('site', models.OneToOneField(help_text='关联站点', on_delete=django.db.models.deletion.CASCADE, related_name='refresh_policy', to='sitesearch_api.site')),
            ],
            options={
                'db_table': 'sitesearch_refresh_policy',
                'ordering': ['-updated_at'],
            },
        ),
        migrations.AddField(
            model_name='crawlpolicy',
            name='site',
            field=models.ForeignKey(help_text='关联站点', on_delete=django.db.models.deletion.CASCADE, related_name='crawl_policies', to='sitesearch_api.site'),
        ),
        migrations.AlterUniqueTogether(
            name='crawlpolicy',
            unique_together={('site', 'name')},
        ),
    ]
