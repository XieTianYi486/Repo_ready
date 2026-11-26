import { ArrowLeft, Compass } from "lucide-react";
import { Link } from "react-router-dom";
import { Button, PageContainer, Panel } from "../components/ui";

export function NotFoundPage() {
  return (
    <PageContainer className="flex min-h-[70vh] items-center justify-center py-16">
      <Panel className="w-full max-w-lg p-8 text-center">
        <span className="mx-auto mb-5 inline-flex h-14 w-14 items-center justify-center rounded-2xl border border-line bg-surface-2 text-accent-2">
          <Compass size={26} aria-hidden="true" />
        </span>
        <p className="font-mono text-xs text-muted">404 / NOT FOUND</p>
        <h1 className="mt-2 text-2xl font-semibold text-ink">这个页面不存在</h1>
        <p className="mt-2 text-sm leading-6 text-muted">
          报告可能已过期，或者链接输入有误。回到首页重新发起一次体检即可。
        </p>
        <Link to="/" className="mt-6 inline-block">
          <Button variant="primary">
            <ArrowLeft size={15} aria-hidden="true" />
            返回首页
          </Button>
        </Link>
      </Panel>
    </PageContainer>
  );
}
